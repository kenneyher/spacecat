import socket

HOST:str = "127.0.0.1"
PORT:int = 12345

def request_user(sock:socket.socket, uname: str) -> None:
    sock.send(f"/user {uname}".encode())

def send_msg(sock:socket.socket, msg:str) -> None:
    sock.sendall(f"/send {msg}".encode())


def help() -> None:
    print('/send -> send message to server')
    print('/end -> end connection with server')
    print('/help -> print available options')


def end(sock:socket.socket) -> None:
    sock.close()


ACTIONS:dict = {
    "/send" : send_msg,
    "/end" : end,
    "/help" : help
}

sock:socket.socket = socket.socket(
    family = socket.AF_INET,
    type = socket.SOCK_STREAM
)

sock.connect((HOST, PORT))
instruction = ""
exiting = False

print(f'Connected to {HOST}:{PORT}')

print('Please provide your username ----------------------')
request_user(sock, input('>>> '))

print('Please select the action to perform ---------------')
help()

while not exiting:
    # Input will be parsed with split(), Minecraft style
    command:list[str] = input('>>> ').lower().split(" ")
    if command[0] not in ACTIONS:
        print('Please provide a correct option')
    else:
        if command[0] == "/send":
            ACTIONS[command[0]](sock, " ".join(command[1:]))
            msg = sock.recv(1024)
            print(msg.decode())
        elif command[0] == "/end":
            exiting = True
            ACTIONS[command[0]](sock)
        else:
            ACTIONS[command[0]]()

sock.close()

