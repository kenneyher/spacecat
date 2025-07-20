import socket
import threading

HOST='127.0.0.1'
PORT=12345

sock = socket.socket(
    family = socket.AF_INET,    #AF_INET = IPv4
    type = socket.SOCK_STREAM
)

client_usernames: dict = {}

sock.bind((HOST, PORT))
print(f"Socket bound to {HOST}:{PORT}")

def client_handler(conn:socket.socket) -> None:
    data:str = conn.recv(1024).decode()
    if data.startswith('/user '):
        client_usernames[conn] = data.split(" ")[1]
    else:
        conn.sendall("Expected /user <username> as first message".encode())
        conn.close()
        return
    
    while True:
        data:str = conn.recv(1024).decode()
        if not data:
            break
        msg = data.split(" ")

        if data.startswith('/send'):
            msg_content:str = " ".join(msg[1:])
            user = client_usernames[conn]
            response = f"< {user}: {msg_content}"
            conn.sendall(response.encode())
    
    conn.close()
    print(f"< {client_usernames[conn]} disconnected.")
    del client_usernames[conn]

while True:
    sock.listen()
    conn, addr = sock.accept()
    print(f"Connected by {addr}")
    threading.Thread(target=client_handler, args=(conn,)).start()
            
