import socket

HOST:str = "127.0.0.1"
PORT:int = 12345
ACTIONS:tuple[str] = ('/send', '/exit')

sock:socket.socket = socket.socket(
    family = socket.AF_INET,
    type = socket.SOCK_STREAM
)

sock.connect((HOST, PORT))
instruction = ""
exiting = False

def help() -> None:
    print('/send -> send message to server')
    print('/end -> end connection with server')
    print('/help -> print available options')

print(f'Connected to {HOST}:{PORT}')
print('Please select the action to perform ---------------')
help()

while not exiting:
    instruction:str = input('>>> ').lower()
    if instruction not in ACTIONS:
        print('Please provide a correct option')
    elif instruction == '/send':
        msg = input('> Message content >>>')
        sock.sendall(msg.encode())

        print('<', sock.recv(1024).decode())
    elif instruction == '/end':
        option = ''
        while option not in ('y', 'n', 'yes', 'no'):
            option = input('Exit (Y/N) ?>> ').lower()
            if option in ('y', 'yes'):
                exiting = True
                break
            elif option in ('n', 'no'):
                break
    elif instruction == '/help':
        help()

sock.close()

