import asyncio
import logging
import traceback
from typing import Dict, Set
import services as db


class Server:
    def __init__(self, host="127.0.0.1", port=8888):
        self.HOST = host
        self.PORT = port
        self.clients: Dict[asyncio.StreamWriter, str] = {}      # { writer: username }
        self.active_users: Set[str] = set()  # Currently connected users
        # Remove in-memory rooms - now handled by database
        self.user_rooms: Dict[str, str] = {}  # { username: current_room }
        self.logger = self._setup_logging()

        # Initialize database
        db.init_db()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def _get_writer(self, username: str) -> asyncio.StreamWriter:
        """Get writer for a specific username"""
        if username not in self.active_users:
            return None
        
        for writer, uname in self.clients.items():
            if uname == username:
                return writer
        return None
    
    async def _disconnect(self, writer: asyncio.StreamWriter):
        """Handle client disconnection"""
        if writer in self.clients:
            username = self.clients[writer]
            current_room = self.user_rooms.get(username, "general")
            
            # Remove from active tracking
            del self.clients[writer]
            self.active_users.discard(username)
            
            # Remove from database room tracking
            if current_room:
                db.leave_room(username, current_room)
                self.user_rooms.pop(username, None)

            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

            self.logger.info(f"User @{username} disconnected")
            await self.broadcast(
                f"< [System] @{username} left [#{current_room}]!",
                room=current_room
            )

    async def broadcast(self, msg: str, room: str = None, exclude=None):
        """Broadcast message to users in a room"""
        if not self.clients:
            return

        target_users = set()
        
        if room:
            # Get all users currently in the room from our active tracking
            for username, user_room in self.user_rooms.items():
                if user_room == room and username in self.active_users:
                    target_users.add(username)
        else:
            # Broadcast to all active users
            target_users = self.active_users.copy()
        
        self.logger.info(f"Broadcasting to room '{room}': {msg}")
        disconnected = []

        for writer in self.clients:
            username = self.clients[writer]
            if writer != exclude and username in target_users:
                try:
                    writer.write(f"{msg}\n".encode())
                    await writer.drain()
                except Exception as e:
                    self.logger.error(f"Error broadcasting to @{username}: {e}")
                    disconnected.append(writer)
        
        # Clean up disconnected clients
        for writer in disconnected:
            await self._disconnect(writer)
    
    async def list_rooms(self, writer: asyncio.StreamWriter):
        """List all available rooms"""
        rooms = db.get_all_rooms()
        if not rooms:
            await self.send_to(writer, "< [System] No rooms available")
            return
            
        rooms_text = "< [System] Available Rooms:\n"
        for room in rooms:
            prefix = "\U0001F512 " if room['is_locked'] else "#"
            member_count = room['member_count']
            rooms_text += f"\t[{prefix}{room['name']}] ({member_count} members)\n"
        
        await self.send_to(writer, rooms_text.rstrip())

    async def join_room(self, username: str, room_name: str, is_host: bool = False):
        """Add user to a room"""
        # Update database
        if db.join_room(username, room_name, is_host):
            # Update local tracking
            old_room = self.user_rooms.get(username)
            self.user_rooms[username] = room_name
            
            self.logger.info(f"User @{username} joined room '{room_name}'")
            
            # Notify the room
            await self.broadcast(
                f"< [System] @{username} joined [#{room_name}]",
                room=room_name,
            )
            
            return True
        return False

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        addr = writer.get_extra_info("peername")
        self.logger.info(f"New connection from {addr}")

        try:
            # Authentication loop
            while writer not in self.clients:
                try:
                    # Get username
                    await self.send_to(writer, "Please enter your username:")
                    
                    data = await asyncio.wait_for(reader.readline(), timeout=30.0)
                    if not data:
                        return
                    
                    # Parse username from "/user username" format
                    message = data.decode().strip()
                    if not message.startswith("/user ") or len(message.split()) < 2:
                        await self.send_to(writer, "<! [System] Please use format: /user <username>")
                        continue
                        
                    username = message.split()[1].strip()
                    if not username:
                        await self.send_to(writer, "<! [System] Username cannot be empty")
                        continue
                    
                    if username in self.active_users:
                        await self.send_to(writer, f"<! [System] Username @{username} is already online")
                        continue
                    
                    # Get password
                    await self.send_to(writer, "Please enter your password:")
                    
                    data = await asyncio.wait_for(reader.readline(), timeout=30.0)
                    if not data:
                        return
                    
                    password = data.decode().strip()
                    if not password:
                        await self.send_to(writer, "<! [System] Password cannot be empty")
                        continue
                    
                    # Try to authenticate
                    user_info = db.authenticate_user(username, password)
                    
                    if user_info:
                        # Existing user - login successful
                        self.clients[writer] = username
                        self.active_users.add(username)
                        
                        await self.send_to(
                            writer,
                            f"Welcome back @{username}! You can now start chatting."
                        )
                        self.logger.info(f"User @{username} logged in from {addr}")
                        
                        # Join general room by default
                        await self.join_room(username, "general")
                        break
                        
                    elif not db.user_exists(username):
                        # New user - create account
                        if db.create_user(username, password):
                            self.clients[writer] = username
                            self.active_users.add(username)
                            
                            await self.send_to(
                                writer,
                                f"Welcome @{username}! Your account has been created and you can now start chatting."
                            )
                            self.logger.info(f"New user @{username} registered from {addr}")
                            
                            # Join general room by default
                            await self.join_room(username, "general")
                            break
                        else:
                            await self.send_to(writer, "<! [System] Error creating account. Please try again.")
                    else:
                        # Wrong password
                        await self.send_to(writer, "<! [System] Invalid password. Please try again.")
                        
                except asyncio.TimeoutError:
                    self.logger.warning(f"Client {addr} timed out during authentication")
                    return
            
            # Main message handling loop
            while writer in self.clients:
                try:
                    data = await reader.readline()
                    if not data:
                        break

                    message = data.decode().strip()
                    username = self.clients[writer]
                    current_room = self.user_rooms.get(username, "general")

                    self.logger.info(f"Received from @{username}: {message}")

                    if message.startswith("/exit"):
                        await self.send_to(writer, "< [System] Goodbye!")
                        break
                        
                    elif message.startswith("/send "):
                        content = message[6:]
                        if content.strip():
                            # Save message to database
                            db.save_message(username, current_room, content)
                            
                            await self.broadcast(
                                msg=f"< [#{current_room}] @{username} {content}",
                                room=current_room,
                                exclude=writer
                            )
                            self.logger.info(f"Message from @{username} in #{current_room}: {content}")
                            
                    elif message.startswith("/whisper "):
                        args = message.split(' ', 2)  # Split into max 3 parts
                        if len(args) < 3:
                            await self.send_to(
                                writer,
                                "< [System] Usage: /whisper <username> <message>"
                            )
                        else:
                            target = args[1]
                            content = args[2]
                            
                            # Check if target user exists and is in the same room
                            if (target not in self.active_users or 
                                self.user_rooms.get(target) != current_room):
                                await self.send_to(
                                    writer,
                                    f"< [System] User @{target} not found in this room."
                                )
                            elif not content.strip():
                                await self.send_to(
                                    writer,
                                    "< [System] Whisper message cannot be empty"
                                )
                            else:
                                target_writer = self._get_writer(target)
                                if target_writer:
                                    # Save whisper to database
                                    db.save_message(username, current_room, content, 'whisper')
                                    
                                    await self.send_to(
                                        target_writer,
                                        f"< [#{current_room}] @{username} *whispered* \"{content}\""
                                    )
                                    await self.send_to(
                                        writer,
                                        f"< [System] Whispered to @{target}: \"{content}\""
                                    )
                                    
                    elif message.startswith("/rooms"):
                        await self.list_rooms(writer)
                        
                    elif message.startswith("/room "):
                        # Parse room creation command
                        args = message.split()
                        if len(args) < 2:
                            await self.send_to(
                                writer,
                                "< [System] Usage: /room <roomname> [--locked]"
                            )
                            continue
                        
                        is_locked = "--locked" in args
                        room_name = ""
                        for arg in args:
                            if not "/" in arg and not "--" in arg:
                                room_name = arg
                                break
                        
                        # Check if room already exists
                        if db.get_room_info(room_name):
                            await self.send_to(
                                writer,
                                f"< [System] Room '{room_name}' already exists."
                            )
                            continue
                        
                        # Create room
                        if db.create_room(room_name, is_locked, username):
                            lock_status = "locked" if is_locked else "unlocked"
                            await self.send_to(
                                writer, 
                                f"< [System] Created {lock_status} room [#{room_name}]"
                            )
                            
                            # Leave current room and join new room
                            if current_room:
                                db.leave_room(username, current_room)
                                await self.broadcast(
                                    f"< [System] @{username} left [#{current_room}]",
                                    current_room,
                                )
                            
                            await self.join_room(username, room_name, is_host=True)
                        else:
                            await self.send_to(
                                writer,
                                f"< [System] Error creating room '{room_name}'"
                            )
                            
                    elif message.startswith("/enter "):
                        args = message.split()
                        if len(args) < 2:
                            await self.send_to(
                                writer,
                                "< [System] Usage: /enter <roomname>"
                            )
                            continue
                            
                        room_name = args[1]
                        room_info = db.get_room_info(room_name)
                        
                        if not room_info:
                            await self.send_to(
                                writer,
                                f"< [System] Room '{room_name}' not found"
                            )
                        elif room_info['is_locked']:
                            await self.send_to(
                                writer,
                                f"< [System] Room [#{room_name}] is locked. You need to be invited."
                            )
                        else:
                            # Leave current room
                            if current_room:
                                db.leave_room(username, current_room)
                                await self.broadcast(
                                    f"< [System] @{username} left [#{current_room}]",
                                    current_room,
                                )
                            
                            # Join new room
                            await self.join_room(username, room_name)
                            
                    elif message.startswith("/history"):
                        # Show recent room history
                        history = db.get_room_history(current_room, 20)
                        if history:
                            await self.send_to(writer, f"< [System] Recent messages in [#{current_room}]:")
                            for msg in history:
                                timestamp = msg['created_at'][:19]  # Remove microseconds
                                if msg['message_type'] == 'whisper':
                                    continue  # Don't show whispers in history
                                await self.send_to(
                                    writer, 
                                    f"  [{timestamp}] @{msg['username']}: {msg['content']}"
                                )
                        else:
                            await self.send_to(writer, f"< [System] No message history for [#{current_room}]")
                    elif message.startswith("/knock"):
                        args = message.split(" ")
                        if len(args) < 2:
                            await self.send_to(
                                writer,
                                "< [System] /knock should be used with <roomname>"
                            )
                            continue

                        room_name = args[1]
                        room_info = db.get_room_info(room_name)


                        if not room_info:
                            await self.send_to(
                                writer,
                                f"< [System] Could not resolve room [#{room_name}]"
                            )
                            continue
                        else:
                            self.logger.info(
                                f"< [System] {username} `/knock`ed room {room_name} with {room_info}"
                            )
                            host = room_info['created_by']
                            if host == username:
                                await self.send_to(
                                    writer,
                                    "< [System] Cannot invite yourself to a room you created"
                                )
                            else:
                                if not room_info["is_locked"]:
                                    await self.send_to(
                                        writer,
                                        f"< [System] Room [#{room_name}] is unlocked. Use /enter {room_name} to join"
                                    )
                                else:
                                    await self.send_to(
                                        writer,
                                        f"< [System] Invitation sent to host!"
                                    )
                                    db.save_request(username, room_name)
                    elif message.startswith("/peephole"):
                        room_info = db.get_room_info(current_room)

                        if room_info['created_by'] != username:
                            await self.send_to(
                                writer,
                                "< [System] Only the host can see knock requests on this room."
                            )
                            continue
                        elif not room_info['is_locked']:
                            await self.send_to(
                                writer,
                                "< [System] This is not a private room. Knocks are only available for private rooms."
                            )
                            continue
                        else:
                            requests = db.get_requests(current_room)

                            if not requests:
                                await self.send_to(
                                    writer,
                                    "< [System] There is no one at the door!"
                                )
                                continue
                            else:
                                self.logger.info(requests)
                    else:
                        await self.send_to(
                            writer,
                            "< [System] Unknown command. Available: /send, /whisper, /rooms, /room, /enter, /history, /exit"
                        )
                        
                except asyncio.IncompleteReadError:
                    break
                except Exception as e:
                    traceback.print_exc()
                    self.logger.error(f"Error handling message from @{username}: {e}")
                    
        except Exception as e:
            traceback.print_exc()
            self.logger.error(f"Error handling client {addr}: {e}")
        finally:
            await self._disconnect(writer)

    async def send_to(self, writer: asyncio.StreamWriter, message: str):
        """Send message to a specific client"""
        try:
            writer.write(f"{message}\n".encode("utf-8"))
            await writer.drain()
        except Exception as e:
            self.logger.error(f"Error sending message to client: {e}")

    async def start(self):
        """Start the chat server"""
        server = await asyncio.start_server(
            client_connected_cb=self.handle_client,
            host=self.HOST,
            port=self.PORT
        )
        addr = server.sockets[0].getsockname()
        self.logger.info(f"Chat server started on {addr[0]}:{addr[1]}")
        print(f"Chat server running on {addr[0]}:{addr[1]}")
        print("Press Ctrl+C to stop the server")

        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    server = Server()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\n< [SERVER] Server stopped manually")
    except Exception as e:
        print(f"< [SERVER] Server error: {e}")