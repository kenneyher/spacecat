import socket
import threading

class Server:
    def __init__(self, host:str="127.0.0.1", port:int=55555):
        self.HOST = host
        self.PORT = port
        self.server = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM
        )
        self.server.bind((self.HOST, self.PORT))
        self.server.listen()

        self.users = {}      # { conn: uname }

    def broadcast(self, msg:str, exclude=None):
        for c in self.users.keys():
            if c != exclude:
                try:
                    c.send(msg.encode())
                except Exception as e:
                    print(f"<! [SystemERROR] Error broadcasting message: {e}")
    
    def send_online_users(self, client:socket.socket):
        msg:str = "\n< [System] Online users:"
        for c in self.users.values():
            msg += f"  @{c}\n"
        msg += "\n< [System] End of user list."
        client.send(msg.encode())

    def handle_client(self, client:socket.socket):
        uname:str = None
        welcome:str = b"< [System] Welcome to spacecat chatroom!\n"
        welcome += b"< [System] What should we call you?\n"
        client.send(welcome)

        while True:
            try:
                req:str = client.recv(1024).decode().strip()
                if not req:
                    continue

                if req.lower().startswith("/user"):
                    uname = req.split(" ", 1)[1].strip()
                    self.users[client] = uname
                    msg:str = f"< [System] @{uname} joined the chat!\n"
                    self.broadcast(msg)
                elif req.lower().startswith("/send"):
                    content:str = req.split(" ", 1)[1]
                    msg:str = f"\n< @{uname}: {content}"
                    self.broadcast(msg, exclude=client)
                elif req.lower() == "/online":
                    self.send_online_users(client)
                elif req.lower() == "/exit":
                    if client in self.users:
                        name = self.users.pop(client)
                        self.broadcast(f"\n< [System] @{name} left the chatroom!")
                    client.send(b"\n< [System] Goodbye!")
                    client.close()
                    break
                else:
                    print(req)
            except Exception as e:
                print(f"\n<! [SystemERROR] Error handling client: {e}")
                break
        if client in self.users:
            name = self.users.pop(client)
            self.broadcast(f"\n< [System] @{name} left the chatroom!")
        client.close()
    
    def start(self):
        print(f"<! [SERVER] Server started on {self.HOST}:{self.PORT}")
        while True:
            client, addr = self.server.accept()
            print(f"<! [SERVER] New connection from {addr}")
            threading.Thread(
                target=self.handle_client,
                args=(client,),
                daemon=True
            ).start()


if __name__ == "__main__":
    server = Server()
    server.start()