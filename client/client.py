import socket

HOST = "127.0.0.1"
PORT = 12345

sock = socket.socket(
    family = socket.AF_INET,
    type = socket.SOCK_STREAM
)

sock.connect((HOST, PORT))
msg = input("Enter message to server >> ")
sock.sendall(msg.encode())
data = sock.recv(1024)
print(f"received: {data.decode()}")