import sys
import os.path
import uuid
from glob import glob
from datetime import datetime
import os
import re
import mimetypes
from pathlib import Path

class AdvancedHttpProcessor:
    """Enhanced HTTP request processor with advanced file operations"""
    
    def __init__(self, storage_path="server_files"):
        self.client_sessions = {}
        self.storage_directory = storage_path
        self.content_type_mappings = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg', 
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.htm': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.zip': 'application/zip',
            '.rar': 'application/x-rar-compressed',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.bin': 'application/octet-stream'
        }
        self.initialize_storage()
        
    def initialize_storage(self):
        """Create storage directory if it doesn't exist"""
        if not os.path.exists(self.storage_directory):
            os.makedirs(self.storage_directory)
            print(f"Created storage directory: {self.storage_directory}")
        
    def build_response(self, status_code=404, status_text='Not Found', content=bytes(), extra_headers={}):
        """Build HTTP response with headers and content"""
        current_time = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        response_headers = [
            f"HTTP/1.1 {status_code} {status_text}\r\n",
            f"Date: {current_time}\r\n",
            "Connection: close\r\n",
            "Server: AdvancedHttpServer/1.5\r\n",
            f"Content-Length: {len(content)}\r\n"
        ]
        
        # Add additional headers
        for header_name, header_value in extra_headers.items():
            response_headers.append(f"{header_name}: {header_value}\r\n")
        
        response_headers.append("\r\n")
        header_section = "".join(response_headers)
        
        # Ensure content is in bytes format
        if not isinstance(content, bytes):
            content = content.encode('utf-8')
            
        return header_section.encode('utf-8') + content

    def parse_form_data(self, request_body, boundary_string):
        """Parse multipart form data for file uploads"""
        try:
            if isinstance(boundary_string, str):
                boundary_string = boundary_string.encode('utf-8')
                
            form_parts = request_body.split(b'--' + boundary_string)
            
            for part in form_parts:
                if b'Content-Disposition' in part and b'filename=' in part:
                    # Extract filename with regex
                    filename_regex = rb'filename="([^"]*)"'
                    match = re.search(filename_regex, part)
                    if not match:
                        continue
                    
                    filename = match.group(1).decode('utf-8')
                    # Security: prevent directory traversal
                    filename = os.path.basename(filename)
                    
                    # Find content after double CRLF
                    content_start_pos = part.find(b'\r\n\r\n')
                    if content_start_pos == -1:
                        continue
                    
                    file_content = part[content_start_pos + 4:]
                    # Clean trailing CRLF
                    if file_content.endswith(b'\r\n'):
                        file_content = file_content[:-2]
                    
                    return filename, file_content
            
            return None, None
            
        except Exception as parse_error:
            print(f"Form data parsing error: {parse_error}")
            return None, None

    def handle_request(self, request_data):
        """Main request handler - processes incoming HTTP requests"""
        try:
            # Validate input data
            if not isinstance(request_data, bytes):
                return self.build_response(400, 'Bad Request', 'Invalid request format')
            
            # Split headers and body
            header_boundary = request_data.find(b"\r\n\r\n")
            if header_boundary < 0:
                return self.build_response(400, 'Bad Request', 'Malformed HTTP request')
            
            header_section = request_data[:header_boundary]
            request_body = request_data[header_boundary+4:]
            
            try:
                # Parse HTTP request line and headers
                header_lines = header_section.decode('utf-8').split("\r\n")
                request_line_parts = header_lines[0].split(" ")
                
                if len(request_line_parts) < 3:
                    return self.build_response(400, 'Bad Request', 'Invalid HTTP request line')
                
                http_method, request_path, http_version = request_line_parts[0], request_line_parts[1], request_line_parts[2]
                http_method = http_method.upper()
                
                # Parse headers into dictionary
                request_headers = {}
                for header in header_lines[1:]:
                    if ':' in header:
                        key, value = header.split(':', 1)
                        request_headers[key.strip().lower()] = value.strip()
                
                print(f"Handling request: {http_method} {request_path}")
                
                # Route to appropriate handler
                if http_method == 'POST' and request_path == '/file-upload':
                    return self.handle_upload(request_body, request_headers)
                elif http_method == 'GET':
                    return self.handle_get(request_path, request_headers)
                elif http_method == 'DELETE':
                    return self.handle_delete(request_path, request_headers)
                else:
                    return self.build_response(405, 'Method Not Allowed', 'HTTP method not supported')
                        
            except (IndexError, ValueError, UnicodeDecodeError) as decode_error:
                return self.build_response(400, 'Bad Request', f'Request parsing error: {str(decode_error)}')
            
        except Exception as handler_error:
            print(f"Request handling error: {handler_error}")
            return self.build_response(500, 'Internal Server Error', str(handler_error))

    def handle_upload(self, request_body, headers_dict):
        """Process file upload requests"""
        try:
            content_type = headers_dict.get('content-type', '')
            
            if 'multipart/form-data' in content_type:
                # Handle multipart upload
                boundary_match = re.search(r'boundary=([^;]+)', content_type)
                if not boundary_match:
                    return self.build_response(400, 'Bad Request', 'Boundary not found in multipart request')
                
                boundary = boundary_match.group(1)
                filename, file_data = self.parse_form_data(request_body, boundary)
                
                if not filename or file_data is None:
                    return self.build_response(400, 'Bad Request', 'No valid file found in request')
                
            else:
                # Handle direct binary upload
                filename = headers_dict.get('x-upload-filename')
                if not filename:
                    # Try Content-Disposition header as fallback
                    content_disposition = headers_dict.get('content-disposition', '')
                    filename_match = re.search(r'filename="([^"]*)"', content_disposition)
                    if filename_match:
                        filename = filename_match.group(1)
                
                if not filename:
                    filename = f'uploaded_file_{int(datetime.now().timestamp())}'
                    
                file_data = request_body
            
            # Validate filename
            if not filename:
                return self.build_response(400, 'Bad Request', 'Filename is required')
            
            # Security: sanitize filename
            safe_filename = os.path.basename(filename)
            if not safe_filename or safe_filename.startswith('.'):
                safe_filename = f"file_{int(datetime.now().timestamp())}"
            
            # Save file to storage directory
            file_path = os.path.join(self.storage_directory, safe_filename)
            with open(file_path, 'wb') as output_file:
                output_file.write(file_data)
            
            success_msg = f'File {safe_filename} uploaded successfully ({len(file_data)} bytes)'
            return self.build_response(201, 'Created', success_msg)
            
        except Exception as upload_error:
            return self.build_response(500, 'Internal Server Error', f'Upload failed: {str(upload_error)}')

    def handle_get(self, request_path, headers_dict):
        """Handle GET requests for files and directory listing"""
        if request_path == '/':
            welcome_message = 'Advanced HTTP File Server - Upload files to /file-upload'
            return self.build_response(200, 'OK', welcome_message)
            
        elif request_path == '/redirect':
            return self.build_response(302, 'Found', '', {'Location': 'https://youtu.be/dQw4w9WgXcQ'})
            
        elif request_path == '/status':
            return self.build_response(200, 'OK', 'Server is running normally')
            
        elif request_path == '/directory':
            try:
                # List files in storage directory
                file_entries = []
                for item in os.listdir(self.storage_directory):
                    item_path = os.path.join(self.storage_directory, item)
                    if os.path.isfile(item_path):
                        file_size = os.path.getsize(item_path)
                        file_entries.append(f"{item} ({file_size} bytes)")
                
                file_listing = "\n".join(file_entries) if file_entries else "No files in directory"
                return self.build_response(200, 'OK', file_listing, {'Content-Type': 'text/plain'})
                
            except Exception as listing_error:
                return self.build_response(500, 'Server Error', str(listing_error))
        
        # Serve individual files
        requested_file = request_path[1:]  # Remove leading slash
        full_file_path = os.path.join(self.storage_directory, requested_file)
        
        if not requested_file or not os.path.isfile(full_file_path):
            return self.build_response(404, 'Not Found', f'File {requested_file} not found')
        
        try:
            with open(full_file_path, 'rb') as file_handle:
                file_content = file_handle.read()
            
            # Determine MIME type
            file_extension = os.path.splitext(requested_file)[1].lower()
            mime_type = self.content_type_mappings.get(file_extension, 'application/octet-stream')
            
            return self.build_response(200, 'OK', file_content, {'Content-Type': mime_type})
            
        except Exception as serve_error:
            return self.build_response(500, 'Internal Server Error', str(serve_error))

    def handle_delete(self, request_path, headers_dict):
        """Handle file deletion requests"""
        requested_file = request_path[1:]  # Remove leading slash
        full_file_path = os.path.join(self.storage_directory, requested_file)
        
        if not requested_file or not os.path.exists(full_file_path):
            return self.build_response(404, 'Not Found', f'File {requested_file} not found')
        
        try:
            os.remove(full_file_path)
            success_msg = f'File {requested_file} deleted successfully'
            return self.build_response(200, 'OK', success_msg)
            
        except Exception as delete_error:
            return self.build_response(500, 'Internal Server Error', str(delete_error))