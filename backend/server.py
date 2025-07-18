import socket

IP_ADDR='127.0.0.1'
PORT=12345

sock = socket.create_server((IP_ADDR, PORT))

print(sock)
