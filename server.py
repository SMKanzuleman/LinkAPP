"""
Secure Chat Server
Features: Authentication, 1-to-1 messaging, Groups with PIN, Voice/Video calls, File sharing
Fixed: Group visibility for creator, Added 'Add User' feature for creator
"""
import socket
import threading
import json
import time
import base64
import sqlite3
import hashlib

# Configuration
HOST = '0.0.0.0'
TCP_PORT = 5556
UDP_AUDIO_PORT = 5557
UDP_VIDEO_PORT = 5558
HEADER_LENGTH = 10
DB_FILE = 'chat.db'

# Encryption key for database
ENCRYPTION_KEY = "SecureKey2024"

# Message types
MSG_SIGNUP = 'signup'
MSG_LOGIN = 'login'
MSG_PRIVATE = 'private'
MSG_FILE = 'file'
MSG_VOICE_MSG = 'voice_msg'
MSG_CALL = 'call'
MSG_CALL_ACCEPT = 'call_accept'
MSG_CALL_REJECT = 'call_reject'
MSG_GROUP_CREATE = 'group_create'
MSG_GROUP_JOIN = 'group_join'
MSG_GROUP_LEAVE = 'group_leave'
MSG_GROUP_MSG = 'group_msg'
MSG_GROUP_FILE = 'group_file'
MSG_GROUP_CALL = 'group_call'
MSG_GROUP_CALL_ACCEPT = 'group_call_accept'
MSG_GROUP_VOICE = 'group_voice_msg'
MSG_GROUP_ADD_USER = 'group_add_user' # New message type
MSG_HISTORY = 'req_history'

# Helper functions
def send_json(sock, data):
    """Send JSON data with length header"""
    try:
        json_str = json.dumps(data)#convert into string
        msg = json_str.encode('utf-8')
        header = str(len(msg)).encode('utf-8').ljust(HEADER_LENGTH)
        sock.sendall(header + msg)
        return True
    except:
        return False

def receive_json(sock):
    """Receive JSON data with length header"""
    try:
        header = sock.recv(HEADER_LENGTH)
        if not header:
            return None
        msg_len = int(header.decode('utf-8').strip())
        data = b''
        while len(data) < msg_len:
            chunk = sock.recv(min(msg_len - len(data), 4096))
            if not chunk:
                return None
            data += chunk
        return json.loads(data.decode('utf-8'))#again become dictonary
    except:
        return None

def encrypt_data(text):
    """Simple XOR encryption for database"""
    if not text:
        return None
    result = bytes([ord(c) ^ ord(ENCRYPTION_KEY[i % len(ENCRYPTION_KEY)]) 
                    for i, c in enumerate(text)])
    return base64.b64encode(result).decode('utf-8')

def decrypt_data(encrypted):
    """Decrypt XOR encrypted data"""
    try:
        if not encrypted:
            return None
        data = base64.b64decode(encrypted)
        result = ''.join([chr(b ^ ord(ENCRYPTION_KEY[i % len(ENCRYPTION_KEY)])) 
                         for i, b in enumerate(data)])
        return result
    except:
        return "[Error]"

def hash_password(password):
    """Hash password with SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

class ChatServer:
    def __init__(self):
        # Initialize database
        self.db_lock = threading.RLock()
        self.init_database()
        
        # Client tracking
        self.clients = {}  # username -> socket
        self.udp_audio_clients = {}  # username -> address
        self.udp_video_clients = {}  # username -> address
        self.group_calls = {}  # room_name -> [participants]
        
        # Setup sockets
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind((HOST, TCP_PORT))
        self.tcp_socket.listen()
        
        self.udp_audio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_audio.bind((HOST, UDP_AUDIO_PORT))
        
        self.udp_video = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_video.bind((HOST, UDP_VIDEO_PORT))
        
        print(f"[SERVER] Started on {HOST}")
        print(f"[SERVER] TCP: {TCP_PORT}, Audio: {UDP_AUDIO_PORT}, Video: {UDP_VIDEO_PORT}")
    
    def init_database(self):
        """Initialize SQLite database with encrypted storage"""
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        c = conn.cursor()
        
        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )''')
        
        # Messages table (encrypted content)
        c.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            content TEXT NOT NULL,
            msg_type TEXT NOT NULL,
            timestamp REAL NOT NULL
        )''')
        
        # Groups table (encrypted)
        c.execute('''CREATE TABLE IF NOT EXISTS groups (
            name TEXT PRIMARY KEY,
            pin_hash TEXT NOT NULL,
            creator TEXT NOT NULL,
            members TEXT NOT NULL,
            created_at REAL NOT NULL
        )''')
        
        conn.commit()
        self.db = conn
        print("[DATABASE] Initialized successfully")
    
    def start(self):
        """Start server threads"""
        threading.Thread(target=self.udp_audio_relay, daemon=True).start()
        threading.Thread(target=self.udp_video_relay, daemon=True).start()
        
        print("[SERVER] Ready for connections")
        while True:
            try:
                conn, addr = self.tcp_socket.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
            except Exception as e:
                print(f"[ERROR] Accept failed: {e}")
    
    def handle_client(self, conn, addr):
        """Handle individual client connection"""
        username = None
        try:
            while True:
                msg = receive_json(conn)
                if not msg:
                    break
                
                msg_type = msg.get('type')
                
                # Authentication
                if msg_type == MSG_SIGNUP:
                    self.handle_signup(conn, msg)
                
                elif msg_type == MSG_LOGIN:
                    username = self.handle_login(conn, msg)
                    if username:
                        self.clients[username] = conn #Dictionary
                        self.broadcast_user_list()
                        self.send_groups_list(conn, username)
                
                # Messaging
                elif msg_type == MSG_PRIVATE:
                    self.handle_private_message(conn, username, msg)
                
                elif msg_type == MSG_FILE:
                    self.handle_file_transfer(conn, username, msg)
                
                elif msg_type == MSG_VOICE_MSG:
                    self.handle_voice_message(conn, username, msg)
                
                elif msg_type == MSG_HISTORY:
                    self.send_message_history(conn, username, msg.get('with'))
                
                # Calls
                elif msg_type in [MSG_CALL, MSG_CALL_ACCEPT, MSG_CALL_REJECT]:
                    self.relay_call_signal(username, msg)
                
                # Groups
                elif msg_type == MSG_GROUP_CREATE:
                    self.handle_group_create(conn, username, msg)
                
                elif msg_type == MSG_GROUP_JOIN:
                    self.handle_group_join(conn, username, msg)
                
                elif msg_type == MSG_GROUP_LEAVE:
                    self.handle_group_leave(conn, username, msg)
                
                elif msg_type == MSG_GROUP_MSG:
                    self.handle_group_message(conn, username, msg)
                
                elif msg_type == MSG_GROUP_FILE:
                    self.handle_group_file(conn, username, msg)
                
                elif msg_type == MSG_GROUP_CALL:
                    self.handle_group_call(conn, username, msg)
                
                elif msg_type == MSG_GROUP_CALL_ACCEPT:
                    self.handle_group_call_accept(conn, username, msg)
                
                elif msg_type == MSG_GROUP_VOICE:
                    self.handle_group_voice(conn, username, msg)

                elif msg_type == MSG_GROUP_ADD_USER:
                    self.handle_group_add_user(conn, username, msg)
        
        except Exception as e:
            print(f"[ERROR] Client {username or addr}: {e}")
        
        finally:
            if username and username in self.clients:
                del self.clients[username]
                self.broadcast_user_list()
            conn.close()
            print(f"[DISCONNECT] {username or addr}")
    
    def handle_signup(self, conn, msg):
        """Register new user"""
        username = msg.get('username')
        password = msg.get('password')
        
        if not username or not password:
            send_json(conn, {'type': 'auth_result', 'success': False, 'message': 'Invalid credentials'})
            return
        
        with self.db_lock:
            try:
                pwd_hash = hash_password(password)
                self.db.execute("INSERT INTO users VALUES (?, ?)", (username, pwd_hash))
                self.db.commit()
                send_json(conn, {'type': 'auth_result', 'success': True, 'message': 'Account created'})
                print(f"[SIGNUP] {username}")
            except sqlite3.IntegrityError:
                send_json(conn, {'type': 'auth_result', 'success': False, 'message': 'Username exists'})
            except Exception as e:
                send_json(conn, {'type': 'auth_result', 'success': False, 'message': str(e)})
    
    def handle_login(self, conn, msg):
        """Authenticate user"""
        username = msg.get('username')
        password = msg.get('password')
        
        if not username or not password:
            send_json(conn, {'type': 'auth_result', 'success': False, 'message': 'Invalid credentials'})
            return None
        
        with self.db_lock:
            cursor = self.db.execute("SELECT password_hash FROM users WHERE username=?", (username,))
            row = cursor.fetchone()
        
        if row and row[0] == hash_password(password):
            if username in self.clients:
                send_json(conn, {'type': 'auth_result', 'success': False, 'message': 'Already logged in'})
                return None
            send_json(conn, {'type': 'auth_result', 'success': True, 'message': 'Login successful'})
            print(f"[LOGIN] {username}")
            return username
        else:
            send_json(conn, {'type': 'auth_result', 'success': False, 'message': 'Invalid credentials'})
            return None
    
    def handle_private_message(self, conn, sender, msg):
        """Handle private message"""
        receiver = msg.get('to')
        content = msg.get('content')
        
        if not receiver or not content:
            return
        
        # Store encrypted message
        with self.db_lock:
            encrypted_content = encrypt_data(content)
            self.db.execute(
                "INSERT INTO messages (sender, receiver, content, msg_type, timestamp) VALUES (?, ?, ?, ?, ?)",
                (sender, receiver, encrypted_content, 'text', time.time())
            )
            self.db.commit()
        
        # Forward to recipient if online
        if receiver in self.clients:
            send_json(self.clients[receiver], {
                'type': 'private',
                'from': sender,
                'content': content
            })
    
    def handle_file_transfer(self, conn, sender, msg):
        """Handle file transfer"""
        receiver = msg.get('to')
        filename = msg.get('filename')
        content = msg.get('content')
        
        if not receiver or not filename or not content:
            return
        
        # Store file metadata
        with self.db_lock:
            encrypted_meta = encrypt_data(f"FILE:{filename}")
            self.db.execute(
                "INSERT INTO messages (sender, receiver, content, msg_type, timestamp) VALUES (?, ?, ?, ?, ?)",
                (sender, receiver, encrypted_meta, 'file', time.time())
            )
            self.db.commit()
        
        # Forward file if recipient online
        if receiver in self.clients:
            send_json(self.clients[receiver], {
                'type': 'file',
                'from': sender,
                'filename': filename,
                'content': content
            })
    
    def send_message_history(self, conn, username, partner):
        """Send message history"""
        if not partner:
            return
        
        with self.db_lock:
            cursor = self.db.execute(
                """SELECT sender, content, msg_type FROM messages 
                   WHERE (sender=? AND receiver=?) OR (sender=? AND receiver=?)
                   ORDER BY timestamp ASC LIMIT 50""",
                (username, partner, partner, username)
            )
            rows = cursor.fetchall()
        
        history = []
        for sender, encrypted_content, msg_type in rows:
            content = decrypt_data(encrypted_content)
            history.append({
                'sender': sender,
                'content': content,
                'type': msg_type
            })
        
        send_json(conn, {
            'type': 'history',
            'with': partner,
            'data': history
        })
    
    def relay_call_signal(self, sender, msg):
        """Relay call signaling"""
        receiver = msg.get('to')
        if receiver and receiver in self.clients:
            msg['from'] = sender
            send_json(self.clients[receiver], msg)
    
    def handle_group_create(self, conn, creator, msg):
        """Create new group"""
        group_name = msg.get('room_name')
        pin = msg.get('pin')
        
        if not group_name or not pin:
            send_json(conn, {'type': 'text', 'from': 'SYSTEM', 'content': 'Invalid group data'})
            return
        
        with self.db_lock:
            try:
                pin_hash = hash_password(pin)
                members_encrypted = encrypt_data(json.dumps([creator]))
                self.db.execute(
                    "INSERT INTO groups VALUES (?, ?, ?, ?, ?)",
                    (group_name, pin_hash, creator, members_encrypted, time.time())
                )
                self.db.commit()
                send_json(conn, {'type': 'text', 'from': 'SYSTEM', 'content': f"Group '{group_name}' created"})
                self.broadcast_groups_update()
                
                # FIX: Update the creator's "My Groups" list immediately
                self.send_groups_list(conn, creator)
                
                print(f"[GROUP] Created: {group_name} by {creator}")
            except sqlite3.IntegrityError:
                send_json(conn, {'type': 'text', 'from': 'SYSTEM', 'content': 'Group already exists'})

    def handle_group_add_user(self, conn, sender, msg):
        """Add user to group by creator"""
        group_name = msg.get('room_name')
        target_user = msg.get('target_user')

        if not group_name or not target_user:
            return

        with self.db_lock:
            # Check if group exists and sender is creator
            cursor = self.db.execute("SELECT creator, members FROM groups WHERE name=?", (group_name,))
            row = cursor.fetchone()

            if not row:
                send_json(conn, {'type': 'text', 'from': 'SYSTEM', 'content': 'Group not found'})
                return

            creator, encrypted_members = row
            if creator != sender:
                send_json(conn, {'type': 'text', 'from': 'SYSTEM', 'content': 'Only creator can add users'})
                return
            
            # Check if target user exists
            cursor = self.db.execute("SELECT username FROM users WHERE username=?", (target_user,))
            if not cursor.fetchone():
                send_json(conn, {'type': 'text', 'from': 'SYSTEM', 'content': 'User not found'})
                return

            # Update members
            members = json.loads(decrypt_data(encrypted_members) or '[]')
            if target_user in members:
                send_json(conn, {'type': 'text', 'from': 'SYSTEM', 'content': 'User already in group'})
                return
            
            members.append(target_user)
            new_encrypted = encrypt_data(json.dumps(members))
            self.db.execute("UPDATE groups SET members=? WHERE name=?", (new_encrypted, group_name))
            self.db.commit()

            # Notify success
            send_json(conn, {'type': 'text', 'from': 'SYSTEM', 'content': f"Added {target_user} to {group_name}"})
            
            # Refresh target user's group list if they are online
            if target_user in self.clients:
                 self.send_groups_list(self.clients[target_user], target_user)
                 send_json(self.clients[target_user], {'type': 'text', 'from': 'SYSTEM', 'content': f"You were added to '{group_name}'"})

            # Notify group
            self.broadcast_to_group(group_name, {'type': 'group_msg', 'room_name': group_name, 
                                                'from': 'SYSTEM', 'content': f"{target_user} added by creator"})
   
    def handle_group_join(self, conn, username, msg):
        """Join existing group"""
        group_name = msg.get('room_name')
        pin = msg.get('pin')
        
        if not group_name or not pin:
            return
        
        with self.db_lock:
            cursor = self.db.execute("SELECT pin_hash, members FROM groups WHERE name=?", (group_name,))
            row = cursor.fetchone()
            
            if not row:
                send_json(conn, {'type': 'text', 'from': 'SYSTEM', 'content': 'Group not found'})
                return
            
            pin_hash, encrypted_members = row
            
            if hash_password(pin) != pin_hash:
                send_json(conn, {'type': 'text', 'from': 'SYSTEM', 'content': 'Incorrect PIN'})
                return
            
            # Safe load with strict string fallback to satisfy type checkers
            members = json.loads(decrypt_data(encrypted_members) or '[]')
            
            if username in members:
                send_json(conn, {'type': 'text', 'from': 'SYSTEM', 'content': 'Already in group'})
                return
            
            members.append(username)
            new_encrypted = encrypt_data(json.dumps(members))
            self.db.execute("UPDATE groups SET members=? WHERE name=?", (new_encrypted, group_name))
            self.db.commit()
            
            send_json(conn, {'type': 'text', 'from': 'SYSTEM', 'content': f"Joined '{group_name}'"})
            self.send_groups_list(conn, username)
            self.broadcast_to_group(group_name, {'type': 'group_msg', 'room_name': group_name, 
                                                  'from': 'SYSTEM', 'content': f"{username} joined"})
            print(f"[GROUP] {username} joined {group_name}")
    
    def handle_group_leave(self, conn, username, msg):
        """Leave group"""
        group_name = msg.get('room_name')
        
        if not group_name:
            return
        
        with self.db_lock:
            cursor = self.db.execute("SELECT members FROM groups WHERE name=?", (group_name,))
            row = cursor.fetchone()
            
            if not row:
                return
            
            # Safe load with strict string fallback
            members = json.loads(decrypt_data(row[0]) or '[]')
            
            if username in members:
                members.remove(username)
                new_encrypted = encrypt_data(json.dumps(members))
                self.db.execute("UPDATE groups SET members=? WHERE name=?", (new_encrypted, group_name))
                self.db.commit()
                
                send_json(conn, {'type': 'text', 'from': 'SYSTEM', 'content': f"Left '{group_name}'"})
                self.send_groups_list(conn, username)
                self.broadcast_to_group(group_name, {'type': 'group_msg', 'room_name': group_name,
                                                      'from': 'SYSTEM', 'content': f"{username} left"})
    
    def handle_group_message(self, conn, sender, msg):
        """Handle group message"""
        group_name = msg.get('room_name')
        content = msg.get('content')
        
        if not group_name or not content:
            return
        
        if self.is_group_member(sender, group_name):
            self.broadcast_to_group(group_name, {
                'type': 'group_msg',
                'room_name': group_name,
                'from': sender,
                'content': content
            }, exclude=sender)
    
    def handle_group_file(self, conn, sender, msg):
        """Handle group file transfer"""
        group_name = msg.get('room_name')
        filename = msg.get('filename')
        content = msg.get('content')
        
        if not group_name or not filename or not content:
            return
        
        if self.is_group_member(sender, group_name):
            self.broadcast_to_group(group_name, {
                'type': 'group_file',
                'room_name': group_name,
                'from': sender,
                'filename': filename,
                'content': content
            }, exclude=sender)
    
    def handle_group_call(self, conn, sender, msg):
        """Initiate group call"""
        group_name = msg.get('room_name')
        mode = msg.get('mode', 'audio')
        
        if not group_name:
            return
        
        if self.is_group_member(sender, group_name):
            self.broadcast_to_group(group_name, {
                'type': 'group_call',
                'room_name': group_name,
                'from': sender,
                'mode': mode
            }, exclude=sender)
    
    def handle_group_call_accept(self, conn, username, msg):
        """Accept group call"""
        group_name = msg.get('room_name')
        
        if not group_name:
            return
        
        if group_name not in self.group_calls:
            self.group_calls[group_name] = []
        
        if username not in self.group_calls[group_name]:
            self.group_calls[group_name].append(username)
            print(f"[GROUP CALL] {username} joined {group_name}")
        
        self.broadcast_to_group(group_name, {
            'type': 'group_call_accept',
            'room_name': group_name,
            'from': username
        })
    
    def handle_group_voice(self, conn, sender, msg):
        """Handle group voice message"""
        group_name = msg.get('room_name')
        content = msg.get('content')
        duration = msg.get('duration', 0)
        
        if not group_name or not content:
            return
        
        if self.is_group_member(sender, group_name):
            self.broadcast_to_group(group_name, {
                'type': 'group_voice_msg',
                'room_name': group_name,
                'from': sender,
                'content': content,
                'duration': duration
            }, exclude=sender)
    
    def is_group_member(self, username, group_name):
        """Check if user is group member"""
        with self.db_lock:
            cursor = self.db.execute("SELECT members FROM groups WHERE name=?", (group_name,))
            row = cursor.fetchone()
            if row:
                # Safe load with strict string fallback
                members = json.loads(decrypt_data(row[0]) or '[]')
                return username in members
        return False
    
    def broadcast_to_group(self, group_name, message, exclude=None):
        """Broadcast message to all group members"""
        with self.db_lock:
            cursor = self.db.execute("SELECT members FROM groups WHERE name=?", (group_name,))
            row = cursor.fetchone()
            if not row:
                return
            # Safe load with strict string fallback
            members = json.loads(decrypt_data(row[0]) or '[]')
        
        for member in members:
            if member != exclude and member in self.clients:
                send_json(self.clients[member], message)
    
    def broadcast_user_list(self):
        """Broadcast online users list"""
        with self.db_lock:
            cursor = self.db.execute("SELECT username FROM users")
            all_users = [row[0] for row in cursor.fetchall()]
        
        user_list = [{'username': u, 'status': 'online' if u in self.clients else 'offline'} 
                     for u in all_users]
        
        payload = {'type': 'list', 'users': user_list}
        for client in self.clients.values():
            send_json(client, payload)
    
    def send_groups_list(self, conn, username):
        """Send groups list to user"""
        with self.db_lock:
            cursor = self.db.execute("SELECT name, members, creator FROM groups")
            all_groups = cursor.fetchall()
        
        all_group_names = [row[0] for row in all_groups]
        my_groups = []
        
        for name, encrypted_members, creator in all_groups:
            # Safe load with strict string fallback
            members = json.loads(decrypt_data(encrypted_members) or '[]')
            if username in members:
                # FIX: Send dictionary with Creator info instead of just name string
                my_groups.append({'name': name, 'creator': creator})
        
        send_json(conn, {'type': 'all_groups_list', 'groups': all_group_names})
        send_json(conn, {'type': 'my_groups_list', 'groups': my_groups})
    
    def broadcast_groups_update(self):
        """Broadcast groups update to all clients"""
        with self.db_lock:
            cursor = self.db.execute("SELECT name FROM groups")
            all_groups = [row[0] for row in cursor.fetchall()]
        
        payload = {'type': 'all_groups_list', 'groups': all_groups}
        for client in self.clients.values():
            send_json(client, payload)
    
    def udp_audio_relay(self):
        """Relay UDP audio packets"""
        print("[UDP] Audio relay started")
        while True:
            try:
                data, addr = self.udp_audio.recvfrom(4096)
                
                # Registration
                if data.startswith(b'REG:'):
                    username = data.decode().split(':')[1]
                    self.udp_audio_clients[username] = addr
                    continue
                
                # Group call: G<room>\0<data>
                if data.startswith(b'G'):
                    null_idx = data.find(b'\0', 1)
                    if null_idx != -1:
                        room = data[1:null_idx].decode()
                        payload = data[null_idx+1:]
                        if room in self.group_calls:
                            sender = next((u for u, a in self.udp_audio_clients.items() if a == addr), None)
                            if sender:
                                for participant in self.group_calls[room]:
                                    if participant != sender and participant in self.udp_audio_clients:
                                        self.udp_audio.sendto(payload, self.udp_audio_clients[participant])
                
                # Private call: A<target>\0<data>
                elif data.startswith(b'A'):
                    null_idx = data.find(b'\0', 1)
                    if null_idx != -1:
                        target = data[1:null_idx].decode()
                        payload = data[null_idx+1:]
                        if target in self.udp_audio_clients:
                            self.udp_audio.sendto(payload, self.udp_audio_clients[target])
            except Exception as e:
                # print(f"Audio relay error: {e}")
                pass
    
    def udp_video_relay(self):
        """Relay UDP video packets"""
        print("[UDP] Video relay started")
        while True:
            try:
                data, addr = self.udp_video.recvfrom(60000)
                
                # Registration
                if data.startswith(b'REG:'):
                    username = data.decode().split(':')[1]
                    self.udp_video_clients[username] = addr
                    continue
                
                # Group call: H<room>\0<data>
                if data.startswith(b'H'):
                    null_idx = data.find(b'\0', 1)
                    if null_idx != -1:
                        room = data[1:null_idx].decode()
                        payload = data[null_idx+1:]
                        if room in self.group_calls:
                            sender = next((u for u, a in self.udp_video_clients.items() if a == addr), None)
                            if sender:
                                for participant in self.group_calls[room]:
                                    if participant != sender and participant in self.udp_video_clients:
                                        self.udp_video.sendto(payload, self.udp_video_clients[participant])
                
                # Private call: V<target>\0<data>
                elif data.startswith(b'V'):
                    null_idx = data.find(b'\0', 1)
                    if null_idx != -1:
                        target = data[1:null_idx].decode()
                        payload = data[null_idx+1:]
                        if target in self.udp_video_clients:
                            self.udp_video.sendto(payload, self.udp_video_clients[target])
            except Exception as e:
                # print(f"Video relay error: {e}")
                pass

if __name__ == "__main__":
    server = ChatServer()
    server.start()