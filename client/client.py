import socket
import sys
import threading

class Client:
    def __init__(self, host:str = "127.0.0.1", port:int = 12345) -> None:
        self.host:str = host
        self.port:int = port
        self.sock = None
    
    def recieve(self, sock: socket.socket) -> None:
        while True:
            try:
                data:bytes = sock.recv(1024)
                if not data:
                    print("\n< [System] Disconnected from server.")
                    break
                msg:str = data.decode()

                # Erase current input, print msg, and redraw input
                sys.stdout.write('\r' + ' ' * 80 + '\r')  # clear line
                sys.stdout.write(msg)
                sys.stdout.write("> ")
                sys.stdout.flush()
            except Exception as e:
                print(f"<! [SystemERROR] Error receiving data: {e}")
                break
    
    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        
        threading.Thread(
            target=self.recieve,
            args=(sock,),
            daemon=True
        ).start()

        try:
            while True:
                sys.stdout.write("> ")
                sys.stdout.flush()
                uinput:str = sys.stdin.readline().strip()
                if not uinput:
                    continue

                sock.send(uinput.encode())
                if uinput == "/exit":
                    break
        except KeyboardInterrupt:
            sock.send(b"/end")
        except Exception as e:
            print(f"<! [SystemERROR] Error: {e}")
        finally:
            sock.close()


if __name__ == "__main__":
    client = Client()
    client.start()