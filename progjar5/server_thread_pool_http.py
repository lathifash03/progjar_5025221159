import socket
import threading
import queue
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from http import AdvancedHttpProcessor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [Thread:%(thread)d] - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ThreadPoolHttpServer:
    """HTTP Server with Thread Pool for concurrent request handling"""
    
    def __init__(self, bind_host='0.0.0.0', bind_port=8889, thread_count=8, request_queue_size=25):
        self.bind_address = bind_host
        self.bind_port = bind_port
        self.thread_count = thread_count
        self.request_queue_size = request_queue_size
        self.server_socket = None
        self.server_running = False
        self.http_processor = AdvancedHttpProcessor()
        self.thread_pool = None
        self.processed_requests = 0
        self.stats_lock = threading.Lock()
        
    def initialize_server_socket(self):
        """Setup and configure server socket"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Allow socket reuse
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to specified address
            bind_endpoint = (self.bind_address, self.bind_port)
            self.server_socket.bind(bind_endpoint)
            
            # Start listening for connections
            self.server_socket.listen(self.request_queue_size)
            
            logger.info(f"Server socket initialized on {bind_endpoint}")
            return True
            
        except Exception as socket_error:
            logger.error(f"Socket initialization failed: {socket_error}")
            return False
    
    def process_client_request(self, client_socket, client_endpoint):
        """Handle individual client request in thread"""
        request_id = None
        
        try:
            # Generate unique request identifier
            with self.stats_lock:
                self.processed_requests += 1
                request_id = self.processed_requests
            
            logger.info(f"Request #{request_id} from {client_endpoint} - Processing started")
            
            # Configure socket timeout
            client_socket.settimeout(25.0)
            
            # Read request data
            request_buffer = bytearray()
            while True:
                try:
                    data_chunk = client_socket.recv(8192)
                    if not data_chunk:
                        break
                    
                    request_buffer.extend(data_chunk)
                    
                    # Check for complete HTTP request
                    if b'\r\n\r\n' in request_buffer:
                        break
                        
                    # Prevent memory exhaustion
                    if len(request_buffer) > 15 * 1024 * 1024:  # 15MB limit
                        logger.warning(f"Request #{request_id}: Size limit exceeded")
                        break
                        
                except socket.timeout:
                    logger.warning(f"Request #{request_id}: Read timeout")
                    break
            
            if not request_buffer:
                logger.warning(f"Request #{request_id}: No data received")
                return
            
            # Process HTTP request
            logger.debug(f"Request #{request_id}: Processing {len(request_buffer)} bytes")
            response_data = self.http_processor.handle_request(bytes(request_buffer))
            
            # Send response to client
            client_socket.sendall(response_data)
            logger.info(f"Request #{request_id}: Response sent ({len(response_data)} bytes)")
            
        except socket.timeout:
            logger.warning(f"Request #{request_id}: Socket timeout occurred")
        except ConnectionResetError:
            logger.warning(f"Request #{request_id}: Client connection reset")
        except Exception as processing_error:
            logger.error(f"Request #{request_id}: Processing error - {processing_error}")
        finally:
            try:
                client_socket.close()
                logger.debug(f"Request #{request_id}: Connection closed")
            except:
                pass
    
    def monitor_server_performance(self):
        """Monitor server performance and log statistics"""
        while self.server_running:
            try:
                time.sleep(45)  # Report every 45 seconds
                with self.stats_lock:
                    logger.info(f"Server Performance - Requests processed: {self.processed_requests}")
            except Exception:
                break
    
    def start_server(self):
        """Start the thread pool HTTP server"""
        logger.info("Initializing Thread Pool HTTP Server...")
        
        if not self.initialize_server_socket():
            logger.error("Failed to initialize server socket")
            return
        
        self.server_running = True
        
        # Initialize thread pool
        self.thread_pool = ThreadPoolExecutor(
            max_workers=self.thread_count,
            thread_name_prefix="HttpWorker"
        )
        
        # Start performance monitoring thread
        monitor_thread = threading.Thread(target=self.monitor_server_performance, daemon=True)
        monitor_thread.start()
        
        logger.info(f"Server listening on {self.bind_address}:{self.bind_port}")
        logger.info(f"Thread pool initialized with {self.thread_count} worker threads")
        
        try:
            while self.server_running:
                try:
                    # Accept new client connection
                    client_socket, client_endpoint = self.server_socket.accept()
                    
                    # Submit request to thread pool
                    future_task = self.thread_pool.submit(
                        self.process_client_request,
                        client_socket,
                        client_endpoint
                    )
                    
                    # Add completion callback
                    future_task.add_done_callback(lambda task: self.handle_task_completion(task))
                    
                except socket.error as socket_err:
                    if self.server_running:
                        logger.error(f"Socket error: {socket_err}")
                    break
                except Exception as accept_error:
                    logger.error(f"Accept error: {accept_error}")
                    
        except KeyboardInterrupt:
            logger.info("Server shutdown requested")
        finally:
            self.shutdown_server()
    
    def handle_task_completion(self, completed_task):
        """Handle completed thread pool tasks"""
        try:
            completed_task.result()  # Will raise exception if task failed
        except Exception as task_error:
            logger.error(f"Task completion error: {task_error}")
    
    def shutdown_server(self):
        """Gracefully shutdown the server"""
        logger.info("Starting server shutdown...")
        self.server_running = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
                logger.info("Server socket closed")
            except:
                pass
        
        if self.thread_pool:
            logger.info("Shutting down thread pool...")
            self.thread_pool.shutdown(wait=True, timeout=15)
            logger.info("Thread pool shutdown completed")
        
        logger.info("Server shutdown completed successfully")

def main():
    """Main server entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Thread Pool HTTP Server')
    parser.add_argument('--host', default='0.0.0.0', help='Server bind address')
    parser.add_argument('--port', type=int, default=8080, help='Server port number')
    parser.add_argument('--threads', type=int, default=8, help='Number of worker threads')
    parser.add_argument('--queue-size', type=int, default=25, help='Request queue size')
    
    args = parser.parse_args()
    
    # Create and configure server
    http_server = ThreadPoolHttpServer(
        bind_host=args.host,
        bind_port=args.port,
        thread_count=args.threads,
        request_queue_size=args.queue_size
    )
    
    try:
        http_server.start_server()
    except Exception as main_error:
        logger.error(f"Server startup error: {main_error}")
    finally:
        logger.info("Server process terminated")

if __name__ == '__main__':
    main()