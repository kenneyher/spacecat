import socket

HOST='127.0.0.1'
PORT=12345

sock = socket.socket(
    family = socket.AF_INET,    #AF_INET = IPv4
    type = socket.SOCK_STREAM
)

sock.bind((HOST, PORT))
print(f"Socket bound to {HOST}:{PORT}")
sock.listen()
conn, addr = sock.accept()

with conn : 
    print(f"connected by {addr}")
    while True:
        data = conn.recv(1024)
        if not data:
            break
        conn.sendall(data)
            
