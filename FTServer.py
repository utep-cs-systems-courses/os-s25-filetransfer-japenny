#!/usr/bin/env python3
import socket
import sys
import os
import select

sys.path.append("../lib")
from lib import params
from archiver import Archiver

class FileServer:
    def __init__(self, port):
        self.listen_port = port
        self.server_socket = self.create_server_socket()
        self.read_list = [self.server_socket] # List of sockets to monitor for incoming data
        self.clients = {} # Dictionary to track connected clients

    def create_server_socket(self):
        # Initialize and bind the server socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', self.listen_port))
        s.listen(5) # Listen to up to 5 queued connections
        s.setblocking(False) # Set socket to non-blocking mode so that accept() and recv() won't block the loop

        print(f"Server listening on 0.0.0.0:{self.listen_port}")
        return s

    def accept_connection(self):
        # Accept a new client connection and configure it
        conn, addr = self.server_socket.accept()
        conn.setblocking(False)  # Set client socket to non-blocking mode
        print(f"Connection from {addr}")

        self.read_list.append(conn)
        self.clients[conn] = {
            'state': 'header', # Waiting for header
            'buffer': b'', # Buffer for incoming data
            'archive_name': None, # Name of the archive file being received
            'file_size': None, # Size of the incoming file
            'received': 0, # Number of bytes received so far
            'fd_out': None, # Output file descriptor
            'addr': addr, # Client address
        }

    def handle_client(self, sock):
        # process data for existing client
        client = self.clients[sock]
        try:
            data = sock.recv(4096)
            if not data:
                raise ConnectionError("Disconnected") # Client has disconnected

            client['buffer'] += data  # Append data to client buffer

            if client['state'] == 'header':
                self.process_header(sock, client) # Parse header if in header state
            if client['state'] == 'data':
                self.process_data(sock, client) # Receive file data if in data state

        except Exception as e:
            self.close_connection(sock, f"Error: {e}")

    def process_header(self, sock, client):
        # Parse header containing filename and file size
        parts = client['buffer'].split(b'\n', 2)
        name, size, rest = parts

        client['archive_name'] = f"new_{name.decode().strip()}" # Prefix filename with 'new_'
        client['file_size'] = int(size.decode().strip()) # Convert file size to int
        client['buffer'] = rest # Remaining data after header
        client['state'] = 'data' # Move to data-receiving state
        client['fd_out'] = open(client['archive_name'], 'wb') # Open file for writing

    def process_data(self, sock, client):
        # Write incoming file data to file
        remaining = client['file_size'] - client['received'] # Calculate remaining bytes
        chunk = client['buffer'][:remaining] # Extract up to 'remaining' bytes

        if chunk:
            client['fd_out'].write(chunk) # Write chunk to file
            client['received'] += len(chunk) # Update received byte count
            client['buffer'] = client['buffer'][len(chunk):] # Remove written bytes from buffer

        if client['received'] >= client['file_size']:
            # File transfer complete
            client['fd_out'].close()
            print(f"Archive '{client['archive_name']}' saved. Extracting...")
            Archiver().extract(client['archive_name']) # Extract archive contents
            print("Extraction complete.")
            sock.sendall(f"Received and extracted {client['archive_name']}\n".encode())
            self.close_connection(sock, "Transfer complete") # Close connection after processing

    def close_connection(self, sock, reason=""):
        # Clean up and close a client connection
        client = self.clients.get(sock)
        if client:
            try:
                if client.get("fd_out"):
                    client["fd_out"].close()  # Ensure file is closed
            except Exception:
                pass
            print(f"Closing connection {client['addr']}. Reason: {reason}")
        sock.close()
        self.read_list.remove(sock)
        self.clients.pop(sock, None)

    def run(self):
        # Main server loop
        while True:
            readable, _, exceptional = select.select(self.read_list, [], self.read_list)

            for sock in readable:
                if sock is self.server_socket:
                    self.accept_connection()  # New incoming connection
                else:
                    self.handle_client(sock)  # Existing client sent data

            for sock in exceptional:
                self.close_connection(sock, "Exceptional condition")


def main():
    # Parse command-line arguments
    switches_var_defaults = (
        (('-l', '--listenPort'), 'listenPort', 50001), # Default listen port is 50001
        (('-?', '--usage'), "usage", False), # Help flag
    )
    param_map = params.parseParams(switches_var_defaults)
    if param_map['usage']:
        params.usage()

    port = int(param_map['listenPort'])

    # Run the file server
    server = FileServer(port)
    server.run()


if __name__ == "__main__":
    main()