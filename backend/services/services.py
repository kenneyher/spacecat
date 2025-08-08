import sqlite3
import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import pathlib

# Get logger
logger = logging.getLogger(__name__)

PATH = pathlib.Path.home() / "spacecat" / "backend" / "spacecat.db"

def get_db_connection():
    """Get a database connection with row factory for easier access"""
    conn = sqlite3.connect(PATH)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn

def init_db():
    """Initialize the database with required tables"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            # Rooms table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rooms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    is_locked BOOLEAN DEFAULT 0,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (created_by) REFERENCES users (id)
                )
            ''')
            
            # Room members table (for tracking who's in which room)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS room_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER,
                    user_id INTEGER,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_host BOOLEAN DEFAULT 0,
                    FOREIGN KEY (room_id) REFERENCES rooms (id),
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE(room_id, user_id)
                )
            ''')
            
            # Chat messages table (optional - for message history)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER,
                    user_id INTEGER,
                    message_type TEXT DEFAULT 'chat',  -- 'chat', 'whisper', 'system'
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (room_id) REFERENCES rooms (id),
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS knock_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    requested_by INTEGER,
                    room_id INTEGER,
                    accepted BOOLEAN DEFAULT 0,
                    FOREIGN KEY (requested_by) REFERENCES users (id),
                    FOREIGN KEY (room_id) REFERENCES rooms (id)
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_rooms_name ON rooms(name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_room_members_room_user ON room_members(room_id, user_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_messages_room_created ON messages(room_id, created_at)')
            
            # Create default "general" room if it doesn't exist
            cursor.execute('''
                INSERT OR IGNORE INTO rooms (name, is_locked, created_by) 
                VALUES ('general', 0, NULL)
            ''')
            
            conn.commit()
            logger.info("Database initialized successfully")
            
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def hash_password(password: str) -> str:
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username: str, password: str) -> bool:
    """Create a new user"""
    try:
        password_hash = hash_password(password)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, password_hash) 
                VALUES (?, ?)
            ''', (username, password_hash))
            conn.commit()
            
        logger.info(f"User '{username}' created successfully")
        return True
        
    except sqlite3.IntegrityError:
        logger.warning(f"Username '{username}' already exists")
        return False
    except Exception as e:
        logger.error(f"Error creating user '{username}': {e}")
        return False

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate a user and return user info if successful"""
    try:
        password_hash = hash_password(password)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, password_hash, created_at, last_login, is_active
                FROM users 
                WHERE username = ? AND password_hash = ? AND is_active = 1
            ''', (username, password_hash))
            
            user_row = cursor.fetchone()
            
            if user_row:
                # Update last login time
                cursor.execute('''
                    UPDATE users SET last_login = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (user_row['id'],))
                conn.commit()
                
                # Convert Row to dict
                user_info = {
                    'id': user_row['id'],
                    'username': user_row['username'],
                    'created_at': user_row['created_at'],
                    'last_login': user_row['last_login'],
                    'is_active': user_row['is_active']
                }
                
                logger.info(f"User '{username}' authenticated successfully")
                return user_info
            else:
                logger.warning(f"Authentication failed for user '{username}'")
                return None
                
    except Exception as e:
        logger.error(f"Error authenticating user '{username}': {e}")
        return None

def user_exists(username: str) -> bool:
    """Check if a user exists"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM users WHERE username = ?', (username,))
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking if user exists: {e}")
        return False

def get_user_by_username(username: str) -> Optional[Dict]:
    """Get user information by username"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, username, created_at, last_login, is_active
                FROM users 
                WHERE username = ? AND is_active = 1
            ''', (username,))
            
            user_row = cursor.fetchone()
            if user_row:
                return {
                    'id': user_row['id'],
                    'username': user_row['username'],
                    'created_at': user_row['created_at'],
                    'last_login': user_row['last_login'],
                    'is_active': user_row['is_active']
                }
            return None
    except Exception as e:
        logger.error(f"Error getting user by username: {e}")
        return None

def create_room(name: str, is_locked: bool = False, created_by_username: str = None) -> bool:
    """Create a new room"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            created_by_id = None
            if created_by_username:
                user_info = get_user_by_username(created_by_username)
                if user_info:
                    created_by_id = user_info['id']
            
            cursor.execute('''
                INSERT INTO rooms (name, is_locked, created_by) 
                VALUES (?, ?, ?)
            ''', (name, is_locked, created_by_id))
            conn.commit()
            
        logger.info(f"Room '{name}' created successfully")
        return True
        
    except sqlite3.IntegrityError:
        logger.warning(f"Room '{name}' already exists")
        return False
    except Exception as e:
        logger.error(f"Error creating room '{name}': {e}")
        return False

def get_room_info(room_name: str) -> Optional[Dict]:
    """Get room information"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.id, r.name, r.is_locked, r.created_at, u.username as created_by
                FROM rooms r
                LEFT JOIN users u ON r.created_by = u.id
                WHERE r.name = ?
            ''', (room_name,))
            
            room_row = cursor.fetchone()
            if room_row:
                return {
                    'id': room_row['id'],
                    'name': room_row['name'],
                    'is_locked': room_row['is_locked'],
                    'created_at': room_row['created_at'],
                    'created_by': room_row['created_by']
                }
            return None
    except Exception as e:
        logger.error(f"Error getting room info: {e}")
        return None

def get_all_rooms() -> List[Dict]:
    """Get all rooms"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT r.id, r.name, r.is_locked, r.created_at, u.username as created_by,
                       COUNT(rm.user_id) as member_count
                FROM rooms r
                LEFT JOIN users u ON r.created_by = u.id
                LEFT JOIN room_members rm ON r.id = rm.room_id
                GROUP BY r.id, r.name, r.is_locked, r.created_at, u.username
                ORDER BY r.created_at
            ''')
            
            rooms = []
            for row in cursor.fetchall():
                rooms.append({
                    'id': row['id'],
                    'name': row['name'],
                    'is_locked': row['is_locked'],
                    'created_at': row['created_at'],
                    'created_by': row['created_by'],
                    'member_count': row['member_count']
                })
            return rooms
    except Exception as e:
        logger.error(f"Error getting all rooms: {e}")
        return []

def join_room(username: str, room_name: str, is_host: bool = False) -> bool:
    """Add a user to a room"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get user and room IDs
            user_info = get_user_by_username(username)
            room_info = get_room_info(room_name)
            
            if not user_info or not room_info:
                return False
            
            cursor.execute('''
                INSERT OR REPLACE INTO room_members (room_id, user_id, is_host) 
                VALUES (?, ?, ?)
            ''', (room_info['id'], user_info['id'], is_host))
            conn.commit()
            
        return True
    except Exception as e:
        logger.error(f"Error joining room: {e}")
        return False

def leave_room(username: str, room_name: str) -> bool:
    """Remove a user from a room"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM room_members 
                WHERE room_id = (SELECT id FROM rooms WHERE name = ?)
                AND user_id = (SELECT id FROM users WHERE username = ?)
            ''', (room_name, username))
            conn.commit()
            
        return True
    except Exception as e:
        logger.error(f"Error leaving room: {e}")
        return False

def is_user_in_room(username: str, room_name: str) -> bool:
    """Check if user is in a specific room"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 1 FROM room_members rm
                JOIN users u ON rm.user_id = u.id
                JOIN rooms r ON rm.room_id = r.id
                WHERE u.username = ? AND r.name = ?
            ''', (username, room_name))
            
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking if user is in room: {e}")
        return False

def save_message(username: str, room_name: str, content: str, message_type: str = 'chat') -> bool:
    """Save a message to the database"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO messages (room_id, user_id, message_type, content)
                SELECT r.id, u.id, ?, ?
                FROM rooms r, users u
                WHERE r.name = ? AND u.username = ?
            ''', (message_type, content, room_name, username))
            conn.commit()
            
        return True
    except Exception as e:
        logger.error(f"Error saving message: {e}")
        return False

def save_request(username: str, room_name: str) -> bool:
    try: 
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO knock_requests (requested_by, room_id, accepted)
                SELECT u.id, r.id, 0
                FROM rooms r
                CROSS JOIN users u
                WHERE r.name = ? AND u.username = ?
            ''', (username, room_name))

            logger.info(f"Saving knock request from {username}")
            conn.commit()
        
        return True
    except Exception as e:
        logger.error(f"Error saving knock requests: {e}")
        return False

def get_room_history(room_name: str, limit: int = 50) -> List[Dict]:
    """Get recent message history for a room"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT u.username, m.content, m.message_type, m.created_at
                FROM messages m
                JOIN users u ON m.user_id = u.id
                JOIN rooms r ON m.room_id = r.id
                WHERE r.name = ?
                ORDER BY m.created_at DESC
                LIMIT ?
            ''', (room_name, limit))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'username': row['username'],
                    'content': row['content'],
                    'message_type': row['message_type'],
                    'created_at': row['created_at']
                })
            return list(reversed(messages))  # Return in chronological order
    except Exception as e:
        logger.error(f"Error getting room history: {e}")
        return []

def get_requests(room_name: str) -> list[str]:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT u.username
                FROM knock_requests kr
                JOIN users u ON kr.requested_by = u.id
                JOIN rooms r ON kr.room_id = r.id
                WHERE r.name = ? AND kr.accepted = 0
            ''', (room_name,))

            results = cursor.fetchall()

            return [row['username'] for row in results]
    except Exception as e:
        logger.error(f"Error getting requests: {e}")
        return []
