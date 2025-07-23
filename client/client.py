import socket
import sys
import threading

class Client:
    def __init__(self, host:str="127.0.0.1", port:int=55555):
        self.HOST = host
        self.PORT = port
        self.client = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM
        )
    

    def receive(self):
        while True:
            try:
                msg:str = self.client.recv(1024).decode()
                if not msg:
                    print("<! [SystemERROR] Connection closed by server.")
                    self.client.close()
                    break
                print(msg, end="")
            except Exception as e:
                print(f"<! [SystemERROR] Error receiving data: {e}")
                self.client.close()
                break
    
    def write(self):
        while True:
            try:
                msg = input("")
                if msg:
                    if not msg.startswith("/"):
                        msg = f"/send {msg}"
                    self.client.send(msg.encode())
                    if msg.lower().strip() == "/exit":
                        break
            except KeyboardInterrupt:
                self.client.send("/exit".encode())
                print("\n<! [System] Connection closed by user.")
                break
        print("< [System] Goodbye!")
        self.client.close()
        sys.exit(0)


    def start(self):
        self.client.connect((self.HOST, self.PORT))

        welcome:str = self.client.recv(1024).decode()
        print(welcome, end="")
        uname:str = input("> ")
        self.client.send(f"/user {uname}".encode())
        
        threading.Thread(
            target=self.receive,
            daemon=True
        ).start()

        self.write()

if __name__ == "__main__":
    client = Client()
    client.start()
