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
        self.attempted_username = None
        self.connected = False
        self.input_queue = Queue()
        self.running = True
        self.room = "general"
    
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
                if message:
                    # Clear the current input line and show the message
                    print(f"\r{' ' * 50}\r{message}")
                    
                    # Check if this is a username setup response
                    if not self.username and self.attempted_username:
                        if "Welcome" in message:
                            self.username = self.attempted_username
                            self.attempted_username = None
                            return  # Exit receive loop during setup
                        elif "already taken" in message or "invalid" in message:
                            self.attempted_username = None
                            print("Username> ", end="", flush=True)
                            continue
                    
                    if f"@{self.username}" in message and f"joined" in message:
                        self.room = re.findall(r'\[(#\w+)\]', message)[0]

                    # Show prompt only if we have a username
                    if self.username:
                        print(f"[{self.room}]> ", end="", flush=True)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error receiving message: {e}")
                break
    
    def show_prompt(self):
        """Show the input prompt"""
        if self.username:
            print(f"[{self.username}]> ", end="", flush=True)
        else:
            print("Username> ", end="", flush=True)
    
    def input_thread(self):
        """Handle input in a separate thread"""
        while self.running:
            try:
                # Don't show prompt here - let the main thread handle it
                user_input = input()
                
                if self.running:  # Check if still running
                    self.input_queue.put(user_input)
            except (EOFError, KeyboardInterrupt):
                if self.running:
                    self.input_queue.put("/exit")
                break
            except Exception as e:
                if self.running:
                    print(f"Input error: {e}")
                break
    
    async def setup_username(self):
        """Handle initial username setup"""
        print("Enter your username: ", end="", flush=True)
        
        # Start input thread
        input_thread = threading.Thread(target=self.input_thread, daemon=True)
        input_thread.start()
        
        while not self.username and self.running:
            try:
                # Check for input with timeout
                await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
                
                if not self.input_queue.empty():
                    username = self.input_queue.get().strip()
                    
                    if username:
                        self.attempted_username = username
                        if await self.send(f"/user {username}"):
                            # Wait for the response to be processed by receive
                            timeout_count = 0
                            while not self.username and self.attempted_username and timeout_count < 50:
                                await asyncio.sleep(0.1)
                                timeout_count += 1
                            
                            if not self.username and timeout_count >= 50:
                                print("\rServer response timeout. Try again.")
                                print("Username> ", end="", flush=True)
                                self.attempted_username = None
                        else:
                            print("\rFailed to send username. Connection lost.")
                            return False
                    else:
                        print("\rUsername cannot be empty.")
                        print("Username> ", end="", flush=True)
                        
            except Exception as e:
                print(f"Setup error: {e}")
                return False
        
        return self.username is not None
    
    async def handle_user_input(self):
        """Handle user input from the queue"""
        # Show initial prompt
        print(f"[{self.room}]> ", end="", flush=True)
        
        while self.connected and self.running:
            try:
                await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
                
                if not self.input_queue.empty():
                    user_input = self.input_queue.get().strip()
                    
                    # print(f"\r{' ' * 50}\r{user_input}") # activate for debugging purposes only
                    if not user_input:
                        print(f"[{self.room}]> ", end="", flush=True)
                        continue
                    
                    if user_input == "/exit":
                        await self.send("/exit")
                        break
                    elif not user_input.startswith("/"):
                        # Clear the input line and show what was typed
                        
                        # Send the message
                        await self.send(f"/send {user_input}")
                        
                        # Show new prompt
                        print(f"[{self.room}]> ", end="", flush=True)
                    else:
                        await self.send(user_input)
                        # Show new prompt
                        print(f"[{self.room}]> ", end="", flush=True)
                    
            except Exception as e:
                print(f"Input handling error: {e}")
                break
    
    async def run(self):
        """Main client loop"""
        if not await self.connect():
            return
        
        try:
            # Start receiving messages first
            receive_task = asyncio.create_task(self.receive())
            
            # Setup username
            if not await self.setup_username():
                receive_task.cancel()
                return
            
            # Cancel the setup receive task and start a new one for chat
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
            
            print("\nYou can now start chatting! Type your messages and press Enter.")
            print("Type '/exit' to quit the chat.\n")
            
            # Start new receive task for chat
            receive_task = asyncio.create_task(self.receive())
            
            # Handle user input
            input_task = asyncio.create_task(self.handle_user_input())
            
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
            print("Disconnected from server.")

async def main():
    client = ChatClient()
    try:
        await client.run()
    except KeyboardInterrupt:
        print("\nClient shutting down...")

if __name__ == "__main__":
    # Handle Windows-specific event loop policy
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())