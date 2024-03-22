import socket
import argparse

def client_send(message, host='127.0.0.1', port=65432):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.sendall(message.encode())
        response = s.recv(1024)
        print(f"Received: {response.decode()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Send a message to a TCP server.')
    parser.add_argument('message', type=str, help='Message to send')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host address of the server (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=65432, help='Port number of the server (default: 65432)')

    args = parser.parse_args()

    # Example usage with command-line arguments
    client_send(args.message, args.host, args.port)
