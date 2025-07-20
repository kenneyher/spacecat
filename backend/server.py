import socket
import threading

HOST='127.0.0.1'
PORT=12345

sock = socket.socket(
    family = socket.AF_INET,    #AF_INET = IPv4
    type = socket.SOCK_STREAM
)

sock.bind((HOST, PORT))
print(f"Socket bound to {HOST}:{PORT}")

def client_handler(conn:socket.socket) -> None:
    data = conn.recv(1024)
    conn.sendall(data)

while True:
    sock.listen()
    conn, addr = sock.accept()
    print(f"Connected by {addr}")
    threading.Thread(target=client_handler, args=(conn,)).start()
            
