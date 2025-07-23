import socket
import threading

HOST='127.0.0.1'
PORT=12345

sock = socket.socket(
    family = socket.AF_INET,    #AF_INET = IPv4
    type = socket.SOCK_STREAM
)

class Server:
    def __init__(self, host:str = '127.0.0.1', port:int = 12345) -> None:
        self.host = host
        self.port = port
        self.sock = socket.socket(
            family = socket.AF_INET,
            type = socket.SOCK_STREAM
        )
        self.clients:dict = {} # { "conn": "uname" }
        self.dms = {}          # { "uname1": "uname2" }

    def broadcast(self, msg:str, sender=None) -> None:
        for conn in self.clients.keys():
            if self.clients[conn] != sender:
                conn.send(msg.encode())
    
    def send_online_users(self, conn:socket.socket) -> None:
        online:str = f"< [System] Online users:\n"
        for uname in self.clients.values():
            online += f"{uname}\n"
        conn.send(online.encode())
    
    def get_conn(self, uname: str) -> socket.socket:
        if uname not in self.clients.values():
            return None
        
        for conn, user in self.clients.items():
            if user == uname:
                return conn
    
    def handle_client(self, conn:socket.socket):
        try:
            welcome:str = b"< [System] Welcome to spacecat chatroom!\n"
            welcome += b"< [System] Provide a username >>> "
            conn.send(welcome)

            uname:str = conn.recv(1024).decode().strip()
            self.clients[conn] = uname

            self.broadcast(f"< [System] {uname} has joined the chatroom!\n")
            self.send_online_users(conn)

            while True:
                request: str = conn.recv(1024).decode().strip()
                if request.lower() == "/help":
                    help_txt = (
                        "< [System] Available commands:\n"
                        "/help - Show this help message\n"
                        "/online - Show online users\n"
                        "/dm <user> - Request a DM session with <user>\n"
                        "/exit - Exit the chatroom\n"
                        "/enconvo - End a DM session\n"
                    )
                    conn.send(help_txt.encode())
                elif request.lower() == "/exit":
                    conn.send(f"< [System] Goodbye!".encode())
                    break
                elif request.lower() == "/online":
                    self.send_online_users(conn)
                elif request.lower().startswith("/dm"):
                    target:str = request[4:].strip()
                    self.start_dm(conn, target)
                elif request.lower() == "/endconvo":
                    if uname not in self.dms:
                        msg:str = b"< [System] Not in a DM. Use /dm <user> to start one.\n"
                        conn.send(msg.encode())
                    else:
                        self.end_dm(conn)
                        conn.send(b"< [System] DM session ended.\n")
                else:
                    if uname in self.dms:
                        partner:str = self.dms[uname]
                        partner_conn:socket.socket = self.get_conn(partner)
                        if not partner_conn:
                            msg:str = f"< [System] [{partner}] is not found.\n"
                            conn.send(msg.encode())
                        elif partner in self.clients.values():
                            msg:str = f"< [{uname}] {request}\n"
                            partner_conn.send(msg.encode())
                    else:
                        msg:str = f"< [System] Not in a DM. Use /dm <user> to start one.\n"
                        conn.send(msg.encode())
        except Exception as e:
            print(f"< [SERVER] Something went wrong: {e}")
            pass
        finally:
            self.end_dm(conn)
            del self.clients[conn]
            self.broadcast(f"< [System] User [{uname}] has left the room.\n")
            conn.close()

    def start_dm(self, conn: socket.socket, target_name:str) -> None:
        target = self.get_conn(target_name)
        if not target:
            msg:str = f"<[System] User [{target_name}] not found.\n"
            conn.send(msg.encode())
            return
        
        req:str = f"< [System] User [{self.clients[conn]}] wants to start a DM session (Y/N) >> "
        target.send(req.encode())
        try:
            response = target.recv(1024).decode().strip().lower()
            if response in "yes":
                self.dms[self.clients[conn]] = target_name
                self.dms[target_name] = self.clients[conn]

                conn.send(f"< [System] [{target_name}] accepted your DM request. Entering chat mode.\n".encode())
                target.send(f"< [System] Entering chat mode with [{self.clients[conn]}]\n".encode())
            else:
                conn.send(f"< [System] [{target_name}] did rejected your DM.\n".encode())
        except:
            conn.send(f"< [System] No reponse from [{target_name}]".encode())
    
    def end_dm(self,conn):
        if conn in self.dms:
            partner:str = self.dms.pop(conn)
            if partner in self.dms:
                self.dms.pop(partner)
                self.get_conn(partner).send(f"< [System] [{self.clients[conn]}] ended the session.\n".encode())
    
    def start(self):
        self.sock.bind((self.host, self.port))
        self.sock.listen()
        print(f"< [SERVER] Started on {self.host}:{self.port}")

        while True:
            conn, addr = self.sock.accept()
            print(f"< [SERVER] New connection from {addr}")
            threading.Thread(target=self.handle_client, args=(conn,)).start()


if __name__ == "__main__":
    server = Server()
    server.start()
