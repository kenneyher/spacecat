import asyncio
import logging
from typing import Dict, Set


class Server:
    def __init__(self, host="127.0.0.1", port=8888):
        self.HOST = host
        self.PORT = port
        self.clients: Dict[asyncio.StreamWriter, str] = {}     # { writer: username }
        self.users: Set[str] = set()
        self.logger = self._setup_logging()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    async def _disconnect(self, writer:asyncio.StreamWriter):
        if writer in self.clients:
            uname = self.clients[writer]
            del self.clients[writer]
            self.users.discard(uname)

            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

            self.logger.info(f"User @{uname} disconnected")
            await self.broadcast(f"< [System] @{uname} left the chat!")

    async def broadcast(self, msg: str, exclude=None):
        if not self.clients:
            return
        
        self.logger.info(f"Broadcasting: {msg}")
        disconnected = []

        for writer in self.clients:
            if writer != exclude:
                try:
                    writer.write(f"{msg}\n".encode())
                    await writer.drain()
                except Exception as e:
                    self.logger.error(f"<! [System] Error broadcasting: {e}")
                    disconnected.append(writer)
        
        for writer in disconnected:
            await self._disconnect(writer)

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        self.logger.info(f"< [Server] New connection from {addr}")

        try:
            while writer not in self.clients:
                try:
                    data = await asyncio.wait_for(
                        reader.readline(), 
                        timeout=30.0
                    )
                    if not data:
                        break

                    message:str = data.decode().strip()
                    if message.startswith('/user '):
                        uname = message[6:].strip()
                        if uname and uname not in self.users:
                            self.clients[writer] = uname
                            self.users.add(uname)
                            await self.send_to(
                                writer,
                                f"Welcome @{uname}! You can now start chatting."
                            )
                            self.logger.info(f"User {uname} joined from {addr}")
                            await self.broadcast(
                                msg=f"< [System] @{uname} joined the room!",
                                exclude=writer
                            )
                        else:
                            await self.send_to(
                                writer,
                                f"<! [System] Username @{uname} is already taken. Try another one"
                            )
                    else:
                        await self.send_to(
                            writer,
                            "Please set your username first with /user <uname>"
                        )
                except asyncio.TimeoutError as e:
                    self.logger.error(f"Client {addr} timed out during uname setup")
                    break
            
            while writer in self.clients:
                try:
                    data = await reader.readline()
                    if not data:
                        break

                    msg:str = data.decode().strip()
                    uname = self.clients[writer]

                    self.logger.info(f"Recieved from {uname}: {msg}")

                    if msg.startswith("/exit "):
                        await self.send_to(
                            writer,
                            f"< [System] Goodbye!"
                        )
                        break
                    elif msg.startswith("/send "):
                        content:str = msg[6:]
                        if content.strip():
                            await self.broadcast(
                                msg=f"< @{uname} {content}",
                                exclude=writer
                            )
                            self.logger.info(f"Sent from @{uname}: {content}")
                    else:
                        await self.send_to(
                            writer,
                            "Unknown command, Use /send <message> or <exit>"
                        )
                except asyncio.IncompleteReadError:
                    break
                except Exception as e:
                    self.logger.error(f"<! [System] Error handling client {addr}: {e}")
        except Exception as e:
            self.logger.error(f"<! [System] Error handling client {addr}: {e}")
        finally:
            await self._disconnect(writer)

    async def send_to(self, writer: asyncio.StreamWriter, msg:str):
        try:
            writer.write(f"{msg}\n".encode())
            await writer.drain()
        except Exception as e:
            self.logger.error(f"Error sendging message to client: {e}")

    async def start(self):
        server = await asyncio.start_server(
            client_connected_cb=self.handle_client,
            host=self.HOST,
            port=self.PORT
        )
        addr = server.sockets[0].getsockname()
        self.logger.info(f"< [SERVER] Server started on {addr}")

        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    server: Server = Server()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\n< [SERVER] Server stopped manually")
    except Exception as e:
        print(f"Server error: {e}")
