import asyncio
import sys
import threading
from queue import Queue
import re

class ChatClient:
    def __init__(self, host='localhost', port=8888):
        self.host = host
        self.port = port
        self.reader = None
        self.writer = None
        self.username = None
        self.current_room = "general"
        self.connected = False
        self.authenticated = False
        self.input_queue = Queue()
        self.running = True
        self.awaiting_password = False
    
    async def connect(self):
        """Connect to the chat server"""
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            self.connected = True
            print(f"Connected to chat server at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the server"""
        self.running = False
        if self.writer:
            try:
                await self.send("/exit")
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
        self.connected = False
    
    async def send(self, message: str):
        """Send message to server"""
        if not self.connected or not self.writer:
            return False
        
        try:
            self.writer.write(f"{message}\n".encode())
            await self.writer.drain()
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
    
    async def receive(self):
        """Continuously receive messages from server"""
        while self.connected and self.reader:
            try:
                data = await self.reader.readline()
                if not data:
                    break
                
                message = data.decode().strip()
                if not message:
                    continue
                
                # Clear current input line and show message
                print(f"\r{' ' * 60}\r{message}")
                
                # Handle authentication responses
                if not self.authenticated:
                    await self._handle_auth_response(message)
                else:
                    # Handle room changes and other updates
                    self._update_room_from_message(message)
                
                # Show appropriate prompt
                self._show_prompt()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error receiving message: {e}")
                break
    
    async def _handle_auth_response(self, message: str):
        """Handle server responses during authentication"""
        if "Please enter your username:" in message:
            self.awaiting_password = False
            print("Username: ", end="", flush=True)
        elif "Please enter your password:" in message:
            self.awaiting_password = True
            print("Password: ", end="", flush=True)
        elif "Welcome" in message and ("@" + str(self.username) if self.username else "") in message:
            self.authenticated = True
            print("\nAuthentication successful!")
        elif any(error in message.lower() for error in ["already taken", "invalid", "cannot be empty", "already online"]):
            # Reset and ask for username again
            self.username = None
            self.awaiting_password = False
    
    def _update_room_from_message(self, message: str):
        """Extract current room from server messages"""
        # Look for room changes in system messages
        if f"@{self.username}" in message and "joined" in message:
            room_match = re.search(r'\[#(\w+)\]', message)
            if room_match:
                self.current_room = room_match.group(1)
        elif "Created" in message and "room" in message:
            room_match = re.search(r'room \[#(\w+)\]', message)
            if room_match:
                self.current_room = room_match.group(1)
    
    def _show_prompt(self):
        """Show appropriate input prompt"""
        if not self.authenticated:
            if self.awaiting_password:
                print("Password: ", end="", flush=True)
            else:
                print("Username: ", end="", flush=True)
        else:
            print(f"[#{self.current_room}]> ", end="", flush=True)
    
    def _input_thread(self):
        """Handle input in a separate thread"""
        while self.running:
            try:
                user_input = input()
                if self.running:
                    self.input_queue.put(user_input)
            except (EOFError, KeyboardInterrupt):
                if self.running:
                    self.input_queue.put("/exit")
                break
            except Exception as e:
                if self.running:
                    print(f"Input error: {e}")
                break
    
    async def _handle_authentication(self):
        """Handle the authentication process"""
        print("Authenticating with server...")
        
        # Start input thread
        input_thread = threading.Thread(target=self._input_thread, daemon=True)
        input_thread.start()
        
        while not self.authenticated and self.running:
            await asyncio.sleep(0.1)
            
            if not self.input_queue.empty():
                user_input = self.input_queue.get().strip()
                
                if not user_input:
                    self._show_prompt()
                    continue
                
                if not self.awaiting_password:
                    # Sending username
                    self.username = user_input
                    await self.send(f"/user {user_input}")
                else:
                    # Sending password
                    await self.send(user_input)
        
        return self.authenticated
    
    async def _handle_chat_input(self):
        """Handle user input during chat"""
        while self.connected and self.running and self.authenticated:
            try:
                await asyncio.sleep(0.1)
                
                if not self.input_queue.empty():
                    user_input = self.input_queue.get().strip()
                    
                    if not user_input:
                        self._show_prompt()
                        continue
                    
                    # Handle exit command
                    if user_input == "/exit":
                        await self.send("/exit")
                        break
                    
                    # Handle special commands
                    elif user_input.startswith("/"):
                        await self.send(user_input)
                    
                    # Handle regular messages
                    else:
                        await self.send(f"/send {user_input}")
                    
                    # Clear input line after sending
                    print(f"\r{' ' * 60}\r", end="", flush=True)
                    self._show_prompt()
                    
            except Exception as e:
                print(f"Input handling error: {e}")
                break
    
    async def run(self):
        """Main client loop"""
        if not await self.connect():
            return
        
        try:
            # Start message receiver
            receive_task = asyncio.create_task(self.receive())
            
            # Handle authentication
            if not await self._handle_authentication():
                print("Authentication failed.")
                return
            
            print("\n" + "="*50)
            print("🎉 Welcome to the chatroom!")
            print("Available commands:")
            print("  • Type messages directly to chat")
            print("  • /whisper <user> <msg> - Send private message")
            print("  • /rooms - List available rooms")
            print("  • /room <name> [--locked] - Create new room")
            print("  • /enter <name> - Join existing room")
            print("  • /history - Show recent messages")
            print("  • /exit - Leave the chat")
            print("="*50)
            print(f"You're now in room: #{self.current_room}")
            self._show_prompt()
            
            # Handle chat input
            input_task = asyncio.create_task(self._handle_chat_input())
            
            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [receive_task, input_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
        except Exception as e:
            print(f"Client error: {e}")
        finally:
            await self.disconnect()
            print("\nDisconnected from server. Goodbye! 👋")

async def main():
    """Main entry point"""
    print("🚀 Starting ChatRoom Client...")
    print("Press Ctrl+C to quit at any time\n")
    
    client = ChatClient()
    try:
        await client.run()
    except KeyboardInterrupt:
        print("\n\nShutting down client...")

if __name__ == "__main__":
    # Handle Windows-specific event loop policy
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())