import socket
import multiprocessing as mp
import signal
import sys
import time
import logging
import os
import threading
from queue import Empty
from http import AdvancedHttpProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [PID:%(process)d] - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def worker_process_function(request_queue, worker_number, bind_address, bind_port):
    """Main function for worker processes"""
    logger.info(f"Worker process {worker_number} started (PID: {os.getpid()})")
    
    # Initialize HTTP processor for this worker
    request_processor = AdvancedHttpProcessor()
    handled_requests = 0
    
    # Setup signal handlers for graceful shutdown
    def shutdown_signal_handler(signal_num, frame):
        logger.info(f"Worker {worker_number} received shutdown signal")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, shutdown_signal_handler)
    signal.signal(signal.SIGINT, shutdown_signal_handler)
    
    try:
        while True:
            try:
                # Retrieve connection from queue with timeout
                connection_data = request_queue.get(timeout=2)
                
                if connection_data is None:  # Shutdown signal
                    logger.info(f"Worker {worker_number} received shutdown command")
                    break
                
                client_socket, client_address = connection_data
                handled_requests += 1
                logger.info(f"Worker {worker_number} processing request #{handled_requests} from {client_address}")
                
                # Handle the client request
                handle_client_connection(client_socket, client_address, request_processor, worker_number)
                
            except:
                # Timeout or other error - continue
                continue
                
    except KeyboardInterrupt:
        logger.info(f"Worker {worker_number} interrupted by user")
    finally:
        logger.info(f"Worker {worker_number} handled {handled_requests} requests, terminating")

def handle_client_connection(client_socket, client_address, processor, worker_id):
    """Process individual client connection in worker process"""
    try:
        client_socket.settimeout(30.0)
        
        # Read incoming request data
        incoming_data = bytearray()
        while True:
            try:
                data_chunk = client_socket.recv(16384)
                if not data_chunk:
                    break
                
                incoming_data.extend(data_chunk)
                
                # Check for complete HTTP request
                if b'\r\n\r\n' in incoming_data:
                    break
                
                # Prevent excessive memory usage
                if len(incoming_data) > 25 * 1024 * 1024:  # 25MB limit
                    logger.warning(f"Worker {worker_id}: Request size exceeded limit")
                    break
                    
            except socket.timeout:
                logger.warning(f"Worker {worker_id}: Client read timeout")
                break
        
        if incoming_data:
            # Process the HTTP request
            http_response = processor.handle_request(bytes(incoming_data))
            
            # Send response back to client
            client_socket.sendall(http_response)
            logger.debug(f"Worker {worker_id}: Response transmitted ({len(http_response)} bytes)")
        
    except Exception as connection_error:
        logger.error(f"Worker {worker_id}: Connection handling error - {connection_error}")
    finally:
        try:
            client_socket.close()
        except:
            pass

class ProcessPoolHttpServer:
    """HTTP Server using process pool for concurrent connection handling"""
    
    def __init__(self, bind_host='0.0.0.0', bind_port=8889, process_count=4):
        self.bind_address = bind_host
        self.bind_port = bind_port
        self.process_count = process_count
        self.server_socket = None
        self.server_active = False
        self.worker_pool = []
        self.request_queue = None
        
    def configure_server_socket(self):
        """Configure and bind server socket"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            server_endpoint = (self.bind_address, self.bind_port)
            self.server_socket.bind(server_endpoint)
            self.server_socket.listen(60)
            
            logger.info(f"Server socket configured on {server_endpoint}")
            return True
            
        except Exception as socket_error:
            logger.error(f"Socket configuration failed: {socket_error}")
            return False
    
    def track_server_statistics(self):
        """Track and log server performance statistics"""
        startup_time = time.time()
        
        while self.server_active:
            try:
                time.sleep(90)  # Report every 90 seconds
                runtime = time.time() - startup_time
                active_workers = sum(1 for w in self.worker_pool if w.is_alive())
                logger.info(f"Server runtime: {runtime:.1f}s, Active processes: {active_workers}")
            except Exception:
                break
    
    def start_server(self):
        """Start the process pool HTTP server"""
        logger.info("Starting Process Pool HTTP Server...")
        
        if not self.configure_server_socket():
            logger.error("Failed to configure server socket")
            return
        
        # Create request queue for inter-process communication
        self.request_queue = mp.Queue(maxsize=150)
        
        # Setup signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self.signal_shutdown_handler)
        signal.signal(signal.SIGTERM, self.signal_shutdown_handler)
        
        self.server_active = True
        
        # Launch worker processes
        for process_num in range(self.process_count):
            worker_process = mp.Process(
                target=worker_process_function,
                args=(self.request_queue, process_num + 1, self.bind_address, self.bind_port),
                name=f"HttpWorker-{process_num + 1}"
            )
            worker_process.start()
            self.worker_pool.append(worker_process)
            logger.info(f"Started worker process {process_num + 1} (PID: {worker_process.pid})")
        
        # Start statistics tracking thread
        stats_thread = threading.Thread(target=self.track_server_statistics, daemon=True)
        stats_thread.start()
        
        logger.info(f"Server operational on {self.bind_address}:{self.bind_port}")
        logger.info(f"Process pool configured with {self.process_count} worker processes")
        
        # Main server acceptance loop
        try:
            while self.server_active:
                try:
                    # Accept incoming client connection
                    client_socket, client_address = self.server_socket.accept()
                    
                    # Queue connection for worker processes
                    try:
                        self.request_queue.put((client_socket, client_address), timeout=2)
                    except:
                        logger.warning("Request queue full, dropping connection")
                        client_socket.close()
                    
                except socket.error as socket_err:
                    if self.server_active:
                        logger.error(f"Socket error occurred: {socket_err}")
                    break
                    
        except Exception as server_error:
            logger.error(f"Server error occurred: {server_error}")
        finally:
            self.terminate_server()
    
    def signal_shutdown_handler(self, signal_num, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signal_num}, initiating server shutdown...")
        self.server_active = False
    
    def terminate_server(self):
        """Gracefully terminate server and all worker processes"""
        logger.info("Terminating process pool server...")
        self.server_active = False
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
                logger.info("Server socket closed")
            except:
                pass
        
        # Send termination signals to all workers
        for _ in self.worker_pool:
            try:
                self.request_queue.put((None, None), timeout=2)
            except:
                pass
        
        # Wait for worker processes to terminate
        logger.info("Waiting for worker processes to terminate...")
        for worker in self.worker_pool:
            try:
                worker.join(timeout=15)
                if worker.is_alive():
                    logger.warning(f"Force terminating worker process {worker.pid}")
                    worker.terminate()
                    worker.join(timeout=3)
            except Exception as termination_error:
                logger.error(f"Error terminating worker: {termination_error}")
        
        logger.info("Process pool server termination completed")

def main():
    """Main entry point for the process pool server"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Process Pool HTTP Server')
    parser.add_argument('--host', default='0.0.0.0', help='Server bind address')
    parser.add_argument('--port', type=int, default=8081, help='Server port number')
    parser.add_argument('--processes', type=int, default=4, help='Number of worker processes')
    
    args = parser.parse_args()
    
    # Limit process count based on system capabilities
    max_allowed_processes = min(args.processes, mp.cpu_count() * 3)
    if max_allowed_processes != args.processes:
        logger.warning(f"Limiting process count to {max_allowed_processes}")
    
    # Create and start server instance
    http_server = ProcessPoolHttpServer(
        bind_host=args.host,
        bind_port=args.port,
        process_count=max_allowed_processes
    )
    
    try:
        http_server.start_server()
    except Exception as startup_error:
        logger.error(f"Server startup failed: {startup_error}")
    finally:
        logger.info("Process pool server process terminated")

if __name__ == '__main__':
    # Set multiprocessing start method for compatibility
    if hasattr(mp, 'set_start_method'):
        try:
            mp.set_start_method('fork', force=True)
        except RuntimeError:
            pass  # Already set
    main()