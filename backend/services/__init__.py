# Services package for chatroom database operations

from .services import (
    # Database initialization
    init_db,
    get_db_connection,

    # User management
    create_user,
    authenticate_user,
    user_exists,
    get_user_by_username,
    hash_password,

    # Room management
    create_room,
    get_room_info,
    get_all_rooms,
    add_room_member,
    remove_room_member,
    is_member_in_room,
    get_room_members,

    # Message handling
    save_message,
    get_room_history,

    # Knock requests
    save_request,
    get_requests,
)

# Make all functions available at package level
__all__ = [
    'init_db',
    'get_db_connection',
    'create_user',
    'authenticate_user',
    'user_exists',
    'get_user_by_username',
    'hash_password',
    'create_room',
    'get_room_info',
    'get_all_rooms',
    'add_room_member',
    'remove_room_member',
    'is_member_in_room',
    'get_room_members',
    'save_message',
    'get_room_history',
    'save_request',
    'get_requests',
]
