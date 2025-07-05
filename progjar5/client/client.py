import sys
import socket
import json
import logging
import ssl
import os
import time
from urllib.parse import quote

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Server configuration
TARGET_HOST = '172.16.16.101'
TARGET_PORT = 8890

class FileTransferClient:
    """HTTP client for file transfer operations"""
    
    def __init__(self, host=TARGET_HOST, port=TARGET_PORT):
        self.server_host = host
        self.server_port = port
        self.connection_timeout = 15
        
    def establish_connection(self, target_host='172.16.16.101', target_port=13000):
        """Create socket connection to server"""
        try:
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            endpoint = (target_host, target_port)
            logger.info(f"Connecting to endpoint {endpoint}")
            client_sock.connect(endpoint)
            return client_sock
        except Exception as conn_error:
            logger.error(f"Connection error: {str(conn_error)}")
            return None

    def transmit_command(self, command_data):
        """Send command to server and receive response"""
        try:
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_sock.settimeout(12.0)
            server_endpoint = (self.server_host, self.server_port)
            client_sock.connect(server_endpoint)
            
            # Format command properly
            if not command_data.endswith('\r\n\r\n'):
                command_data = command_data.replace('\n', '\r\n') + '\r\n'
            
            client_sock.sendall(command_data.encode())
            
            # Receive response
            response_data = b""
            while True:
                data_chunk = client_sock.recv(8192)
                if not data_chunk:
                    break
                response_data += data_chunk
                if len(data_chunk) < 8192:
                    break
            
            return response_data.decode('utf-8', errors='replace')
            
        except socket.timeout:
            return "ERROR: Connection timed out"
        except Exception as transmit_error:
            return f"ERROR: {str(transmit_error)}"
        finally:
            client_sock.close()

    def transmit_binary_data(self, binary_payload):
        """Send binary data to server"""
        try:
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_sock.settimeout(12.0)
            server_endpoint = (self.server_host, self.server_port)
            client_sock.connect(server_endpoint)
            client_sock.sendall(binary_payload)
            
            response_data = b""
            while True:
                data_chunk = client_sock.recv(8192)
                if not data_chunk:
                    break
                response_data += data_chunk
                if len(data_chunk) < 8192:
                    break
                    
            return response_data.decode('utf-8', errors='replace')
            
        except Exception as binary_error:
            return f"ERROR: {str(binary_error)}"
        finally:
            client_sock.close()

    def get_file_directory(self):
        """Retrieve directory listing from server"""
        command = f"""GET /directory HTTP/1.1\r
Host: {self.server_host}\r
User-Agent: FileClient/1.5\r
Accept: text/plain\r

"""
        print("Fetching file directory from server...")
        server_response = self.transmit_command(command)
        print("Server Response:")
        print(server_response)

    def send_file_to_server(self, file_path):
        """Upload file to server using binary transfer"""
        try:
            with open(file_path, 'rb') as file_handle:
                file_bytes = file_handle.read()
        
            filename = os.path.basename(file_path)
            
            # Build HTTP request with file data
            http_request = (
                f"POST /file-upload HTTP/1.1\r\n"
                f"Host: {self.server_host}\r\n"
                f"User-Agent: FileUploader/1.5\r\n"
                f"X-Upload-Filename: {filename}\r\n"
                f"Content-Type: application/octet-stream\r\n"
                f"Content-Length: {len(file_bytes)}\r\n"
                f"\r\n"
            ).encode() + file_bytes

            # Send request to server
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_sock.settimeout(35.0)
            server_endpoint = (self.server_host, self.server_port)
            client_sock.connect(server_endpoint)
            
            try:
                client_sock.sendall(http_request)
                server_response = client_sock.recv(8192)
                print(server_response.decode('utf-8', errors='replace'))
            finally:
                client_sock.close()
                
        except FileNotFoundError:
            print(f"ERROR: File {file_path} not found")
        except Exception as upload_error:
            print(f"Upload error: {str(upload_error)}")

    def remove_file_from_server(self, target_filename):
        """Delete file from server"""
        command = f"""DELETE /{quote(target_filename)} HTTP/1.1\r
Host: {self.server_host}\r
User-Agent: FileClient/1.5\r
Accept: */*\r

"""
        print(f"Deleting file: {target_filename}")
        server_response = self.transmit_command(command)
        print(server_response)

def show_menu():
    """Display operation menu"""
    print("\n" + "="*50)
    print("    FILE TRANSFER CLIENT")
    print("="*50)
    print("1. View server files")
    print("2. Upload file to server")  
    print("3. Delete file from server")
    print("4. Exit")
    print("="*50)

if __name__ == '__main__':
    print("Initializing File Transfer Client...")
    client = FileTransferClient()
    
    while True:
        show_menu()
        user_choice = input("\nChoose operation (1-4): ")
        
        if user_choice == '1':
            client.get_file_directory()
        elif user_choice == '2':
            file_to_upload = input("Enter file path to upload: ")
            if file_to_upload:
                client.send_file_to_server(file_to_upload)
            else:
                print("Invalid file path")
        elif user_choice == '3':
            file_to_delete = input("Enter filename to delete: ")
            if file_to_delete:
                client.remove_file_from_server(file_to_delete)
            else:
                print("Invalid filename")
        elif user_choice == '4':
            print("Exiting client...")
            break
        else:
            print("Invalid choice. Please select 1-4.")