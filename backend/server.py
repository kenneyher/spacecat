import asyncio
import logging
from typing import Dict, Set


class Server:
    def __init__(self, host="127.0.0.1", port=8888):
        self.HOST = host
        self.PORT = port
        self.clients: Dict[asyncio.StreamWriter, str] = {}      # { writer: username }
        self.users: Set[str] = set()
        self.rooms: Dict[str, Set[str]] = {
            "general": set()
        }                    # { room: list[uname] }
        self.logger = self._setup_logging()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def _get_writer(self, uname:str) -> asyncio.StreamWriter:
        if uname not in self.users:
            return None
        
        for writer, username in self.clients.items():
            if uname == username:
                return writer
    
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

    async def broadcast(self, msg: str, room:str=None, exclude=None):
        if not self.clients:
            return

        filter_by_room:bool = False
        if room and room in self.rooms :
            filter_by_room = True
        
        self.logger.info(f"Broadcasting: {msg}")
        disconnected = []

        for writer in self.clients:
            if filter_by_room:
                in_same_room = self.clients[writer] in self.rooms[room]
            else:
                in_same_room = True
            if writer != exclude and in_same_room:
                try:
                    writer.write(f"{msg}\n".encode())
                    await writer.drain()
                except Exception as e:
                    self.logger.error(f"<! [System] Error broadcasting: {e}")
                    disconnected.append(writer)
        
        for writer in disconnected:
            await self._disconnect(writer)
    
    async def list_rooms(self, writer: asyncio.StreamWriter):
        rooms:str = "< [System] Openned Rooms:\n"
        rooms += "\n".join([f"\t[#{room}]" for room in self.rooms])
        await self.send_to(writer, rooms)

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        current_room = "general"
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
                            self.rooms[current_room].add(uname)
                            await self.broadcast(
                                msg=f"< [System] @{uname} joined [#{current_room}]!",
                                room=current_room,
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
                                msg=f"< [#{current_room}] @{uname} {content}",
                                room=current_room,
                                exclude=writer
                            )
                            self.logger.info(f"Sent from @{uname}: {content}")
                    elif msg.startswith("/whisper"):
                        args:list[str] = msg.split(' ')
                        if len(args) < 3:
                            await self.send_to(
                                writer,
                                "< [System] /whisper should have a <user> and a <msg>"
                            )
                        else:
                            self.logger.info("Args for /whisper " + ", ".join(args))
                            target:str = args[1]
                            content:str = " ".join(args[2:])
                            if (
                                target not in self.users or
                                target not in self.rooms[current_room]
                            ):
                                await self.send_to(
                                    writer,
                                    f"< [System] User @{target} could not be resolved."
                                )
                            elif not content.strip():
                                await self.send_to(
                                    writer,
                                    "< [System] /whisper should have a <msg>"
                                )
                            else:
                                target_writer = self._get_writer(target)
                                await self.send_to(
                                    target_writer,
                                    f"< [#{current_room}] @{uname} *whispered* \"{content}\""
                                )
                    elif msg.startswith("/rooms"):
                        await self.list_rooms(writer)
                    elif msg.startswith("/room "):
                        roomname:str = msg.split(' ', 1)[1].strip()
                        self.rooms[current_room].remove(uname)
                        await self.broadcast(
                            f"< [System] @{uname} left [#{current_room}]",
                            current_room,
                        )
                        if roomname not in self.rooms:
                            await self.send_to(
                                writer, 
                                f"< [System] Creating room [#{roomname}]"
                            )
                            self.rooms[roomname] = set()
                        current_room = roomname
                        self.rooms[current_room].add(uname)
                        await self.broadcast(
                            f"< [System] @{uname} joined [#{current_room}]",
                            current_room,
                        )
                    else:
                        await self.send_to(
                            writer,
                            "< [System] Unknown command"
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
