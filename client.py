"""
Secure Chat Client - Tkinter GUI
Features: Login/Register, 1-to-1 chat, Groups with PIN, Voice/Video calls, File sharing
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, font
import socket
import threading
import json
import base64
import time
import os
import sys
from PIL import Image, ImageTk, ImageDraw
import io

# Try importing audio/video libraries
try:
    import pyaudio
    AUDIO_AVAILABLE = True
except:
    AUDIO_AVAILABLE = False
    print("[WARNING] PyAudio not available - voice features disabled")

try:
    import cv2
    VIDEO_AVAILABLE = True
except:
    VIDEO_AVAILABLE = False
    print("[WARNING] OpenCV not available - video features disabled")

# Configuration
DEFAULT_HOST = '127.0.0.1' 
TCP_PORT = 5556
UDP_AUDIO_PORT = 5557
UDP_VIDEO_PORT = 5558
HEADER_LENGTH = 10

# Color Scheme - Deep Ocean Theme
COLORS = {
    'bg_main': '#0f172a',       # Deep Slate Blue (Main window, chat area)
    'bg_panel': '#1e293b',      # Lighter Slate (Sidebar, headers)
    'bg_input': '#334155',      # Slate 700 (Inputs)
    'accent_primary': '#38bdf8', # Sky Blue (Login, active tabs, my messages)
    'accent_secondary': '#4ade80', # Light Green (Register, Call, Open File)
    'accent_danger': '#fb7185',  # Rose (Leave, Reject, End Call)
    'text_primary': '#f8fafc',   # Off-white
    'text_secondary': '#94a3b8', # Slate Grey
    'bubble_me': '#38bdf8',      # Sky Blue
    'bubble_other': '#1e293b',   # Lighter Slate
    'online': '#4ade80',         # Light Green
    'offline': '#fb7185'         # Rose
}

# Helper functions
def send_json(sock, data):
    """Send JSON with length header"""
    try:
        json_str = json.dumps(data)
        msg = json_str.encode('utf-8')
        header = str(len(msg)).encode('utf-8').ljust(HEADER_LENGTH)
        sock.sendall(header + msg)
        return True
    except:
        return False

def receive_json(sock):
    """Receive JSON with length header"""
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
        return json.loads(data.decode('utf-8'))
    except:
        return None

def draw_rounded_rectangle(canvas, x1, y1, x2, y2, radius=20, **kwargs):
    """Draw a rounded rectangle on a canvas"""
    points = [x1+radius, y1,
              x1+radius, y1,
              x2-radius, y1,
              x2-radius, y1,
              x2, y1,
              x2, y1+radius,
              x2, y1+radius,
              x2, y2-radius,
              x2, y2-radius,
              x2, y2,
              x2-radius, y2,
              x2-radius, y2,
              x1+radius, y2,
              x1+radius, y2,
              x1, y2,
              x1, y2-radius,
              x1, y2-radius,
              x1, y1+radius,
              x1, y1+radius,
              x1, y1]
    return canvas.create_polygon(points, **kwargs, smooth=True)

class ChatClient(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Secure Chat")
        self.geometry("900x650")
        self.configure(bg=COLORS['bg_main'])
        
        # State
        self.sock = None
        self.username = None
        self.server_ip = DEFAULT_HOST # Will be updated on login
        self.running = True
        self.active_chat = None
        self.is_group_chat = False
        self.chat_history = {}
        self.group_creators = {} # New: store group creators
        
        # Call state
        self.call_active = False
        self.call_target = None
        self.call_is_group = False # Flag to distinguish call types
        self.call_mode = None
        
        # Setup UI
        self.setup_styles()
        self.show_login_screen()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook", background=COLORS['bg_main'], borderwidth=0)
        style.configure("TNotebook.Tab", background=COLORS['bg_panel'], foreground=COLORS['text_primary'], 
                       padding=[12, 6], font=('Segoe UI', 10, 'bold'))
        style.map("TNotebook.Tab", background=[("selected", COLORS['accent_primary'])])
        
        # Scrollbar style
        style.configure("Vertical.TScrollbar", background=COLORS['bg_panel'], troughcolor=COLORS['bg_main'], borderwidth=0, arrowcolor=COLORS['text_primary'])
    
    def show_login_screen(self):
        """Display login/register screen"""
        for widget in self.winfo_children():
            widget.destroy()
        
        frame = tk.Frame(self, bg=COLORS['bg_main'])
        frame.place(relx=0.5, rely=0.5, anchor='center')
        
        # Title
        tk.Label(frame, text="🔐 Secure Chat", font=('Segoe UI', 28, 'bold'),
                fg=COLORS['accent_primary'], bg=COLORS['bg_main']).pack(pady=20)
        
        # Server IP
        tk.Label(frame, text="Server IP", font=('Segoe UI', 10), 
                fg=COLORS['text_secondary'], bg=COLORS['bg_main']).pack(anchor='w', padx=5)
        self.entry_host = tk.Entry(frame, width=35, font=('Segoe UI', 12),
                                   bg=COLORS['bg_input'], fg=COLORS['text_primary'], insertbackground=COLORS['text_primary'],
                                   relief='flat', bd=5)
        self.entry_host.insert(0, DEFAULT_HOST)
        self.entry_host.pack(pady=(0, 15))
        
        # Username
        tk.Label(frame, text="Username", font=('Segoe UI', 10),
                fg=COLORS['text_secondary'], bg=COLORS['bg_main']).pack(anchor='w', padx=5)
        self.entry_user = tk.Entry(frame, width=35, font=('Segoe UI', 12),
                                   bg=COLORS['bg_input'], fg=COLORS['text_primary'], insertbackground=COLORS['text_primary'],
                                   relief='flat', bd=5)
        self.entry_user.pack(pady=(0, 15))
        
        # Password
        tk.Label(frame, text="Password", font=('Segoe UI', 10),
                fg=COLORS['text_secondary'], bg=COLORS['bg_main']).pack(anchor='w', padx=5)
        self.entry_pass = tk.Entry(frame, width=35, font=('Segoe UI', 12), show='●',
                                   bg=COLORS['bg_input'], fg=COLORS['text_primary'], insertbackground=COLORS['text_primary'],
                                   relief='flat', bd=5)
        self.entry_pass.pack(pady=(0, 20))
        self.entry_pass.bind('<Return>', lambda e: self.authenticate('login'))
        
        # Buttons
        btn_frame = tk.Frame(frame, bg=COLORS['bg_main'])
        btn_frame.pack(pady=10)
        
        self.btn_login = tk.Button(btn_frame, text="Login", font=('Segoe UI', 11, 'bold'),
                                   bg=COLORS['accent_primary'], fg='white', relief='flat', padx=30, pady=8,
                                   command=lambda: self.authenticate('login'))
        self.btn_login.pack(side='left', padx=5)
        
        self.btn_register = tk.Button(btn_frame, text="Register", font=('Segoe UI', 11, 'bold'),
                                      bg=COLORS['accent_secondary'], fg='white', relief='flat', padx=30, pady=8,
                                      command=lambda: self.authenticate('signup'))
        self.btn_register.pack(side='left', padx=5)
    
    def authenticate(self, action):
        """Handle login/register"""
        host = self.entry_host.get().strip()
        username = self.entry_user.get().strip()
        password = self.entry_pass.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Please enter username and password")
            return
        
        # Disable buttons
        self.btn_login.config(state='disabled')
        self.btn_register.config(state='disabled')
        
        # Connect in background thread
        threading.Thread(target=self._auth_thread, args=(action, host, username, password), daemon=True).start()
    
    def _auth_thread(self, action, host, username, password):
        """Background authentication"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((host, TCP_PORT))
            self.sock.settimeout(None)
            
            send_json(self.sock, {'type': action, 'username': username, 'password': password})
            response = receive_json(self.sock)
            
            if response:
                self.after(0, self._auth_result, action, response, username, host)
            else:
                self.after(0, self._auth_error, "No response from server")
        except Exception as e:
            self.after(0, self._auth_error, str(e))
    
    def _auth_result(self, action, response, username, host):
        """Handle authentication result"""
        self.btn_login.config(state='normal')
        self.btn_register.config(state='normal')
        
        if response.get('success'):
            if action == 'login':
                self.username = username
                self.server_ip = host # Store correct server IP
                threading.Thread(target=self.message_listener, daemon=True).start()
                self.show_main_screen()
            else:
                messagebox.showinfo("Success", "Account created! Please login.")
                if self.sock:
                    self.sock.close()
        else:
            messagebox.showerror("Error", response.get('message', 'Authentication failed'))
            if self.sock:
                self.sock.close()
    
    def _auth_error(self, error):
        """Handle authentication error"""
        self.btn_login.config(state='normal')
        self.btn_register.config(state='normal')
        messagebox.showerror("Connection Error", f"Failed to connect: {error}")
        if self.sock:
            self.sock.close()
    
    def show_main_screen(self):
        """Display main chat interface"""
        for widget in self.winfo_children():
            widget.destroy()
        
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Left sidebar
        sidebar = tk.Frame(self, bg=COLORS['bg_panel'], width=250)
        sidebar.grid(row=0, column=0, sticky='ns')
        sidebar.grid_propagate(False)
        
        # User info
        user_frame = tk.Frame(sidebar, bg=COLORS['accent_primary'], height=60)
        user_frame.pack(fill='x')
        user_frame.pack_propagate(False)
        tk.Label(user_frame, text=f"👤 {self.username}", font=('Segoe UI', 13, 'bold'),
                fg='white', bg=COLORS['accent_primary']).pack(pady=18)
        
        # Tabs
        self.notebook = ttk.Notebook(sidebar)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Users tab
        self.tab_users = tk.Frame(self.notebook, bg=COLORS['bg_panel'])
        self.notebook.add(self.tab_users, text='  Users  ')
        self.create_scrollable_list(self.tab_users, 'users')
        
        # Groups tab
        self.tab_groups = tk.Frame(self.notebook, bg=COLORS['bg_panel'])
        self.notebook.add(self.tab_groups, text='  My Groups  ')
        tk.Button(self.tab_groups, text="+ Create Group", command=self.create_group,
                  bg=COLORS['accent_primary'], fg='white', relief='flat', font=('Segoe UI', 9, 'bold')).pack(fill='x', padx=5, pady=5)
        self.create_scrollable_list(self.tab_groups, 'my_groups')
        
        # Explore tab
        self.tab_explore = tk.Frame(self.notebook, bg=COLORS['bg_panel'])
        self.notebook.add(self.tab_explore, text='  Explore  ')
        self.create_scrollable_list(self.tab_explore, 'all_groups')
        
        # Right chat area
        self.chat_area = tk.Frame(self, bg=COLORS['bg_main'])
        self.chat_area.grid(row=0, column=1, sticky='nsew')
        
        # Placeholder
        self.placeholder = tk.Label(self.chat_area, text="Select a user or group to start chatting",
                                    font=('Segoe UI', 14), fg=COLORS['text_secondary'], bg=COLORS['bg_main'])
        self.placeholder.place(relx=0.5, rely=0.5, anchor='center')
    
    def create_scrollable_list(self, parent, list_type):
        """Create scrollable list widget"""
        canvas = tk.Canvas(parent, bg=COLORS['bg_panel'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=COLORS['bg_panel'])
        
        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        if list_type == 'users':
            self.users_list = scroll_frame
        elif list_type == 'my_groups':
            self.my_groups_list = scroll_frame
        elif list_type == 'all_groups':
            self.all_groups_list = scroll_frame
    
    def open_chat(self, target, is_group=False):
        """Open chat window"""
        self.active_chat = target
        self.is_group_chat = is_group
        
        if hasattr(self, 'placeholder'):
            self.placeholder.destroy()
        
        for widget in self.chat_area.winfo_children():
            widget.destroy()
        
        # Header
        header = tk.Frame(self.chat_area, bg=COLORS['bg_panel'], height=60)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        icon = "👥" if is_group else "👤"
        tk.Label(header, text=f"{icon}  {target}", font=('Segoe UI', 14, 'bold'),
                fg=COLORS['text_primary'], bg=COLORS['bg_panel']).pack(side='left', padx=15, pady=15)
        
        # Call buttons
        if not is_group:
            tk.Button(header, text="📹", command=lambda: self.initiate_call(target, 'video'),
                      bg=COLORS['accent_secondary'], fg='white', relief='flat', font=('Arial', 14), width=3).pack(side='right', padx=3, pady=15)
            tk.Button(header, text="📞", command=lambda: self.initiate_call(target, 'audio'),
                      bg=COLORS['accent_primary'], fg='white', relief='flat', font=('Arial', 14), width=3).pack(side='right', padx=3, pady=15)
        else:
            # Group chat header buttons
            # Removed video call button for groups as requested
            tk.Button(header, text="📞 Call", command=lambda: self.initiate_group_call(target, 'audio'),
                      bg=COLORS['accent_primary'], fg='white', relief='flat', font=('Segoe UI', 9), padx=10).pack(side='right', padx=3, pady=15)
            
            # FIX: Show "Add User" button if I am the creator
            creator = self.group_creators.get(target)
            if creator == self.username:
                tk.Button(header, text="+ User", command=lambda: self.add_user_to_group(target),
                        bg=COLORS['accent_secondary'], fg='white', relief='flat', font=('Segoe UI', 9), padx=10).pack(side='right', padx=3, pady=15)
            
            tk.Button(header, text="Leave", command=lambda: self.leave_group(target),
                      bg=COLORS['accent_danger'], fg='white', relief='flat', font=('Segoe UI', 9), padx=10).pack(side='right', padx=3, pady=15)
        
        # Input area (bottom)
        input_frame = tk.Frame(self.chat_area, bg=COLORS['bg_panel'], height=70)
        input_frame.pack(side='bottom', fill='x')
        input_frame.pack_propagate(False)
        
        tk.Button(input_frame, text="📎", command=self.send_file,
                  bg=COLORS['bg_input'], fg='white', relief='flat', font=('Arial', 14), width=3).pack(side='left', padx=5, pady=15)
        
        # Removed voice button as requested
        
        self.entry_msg = tk.Entry(input_frame, font=('Segoe UI', 12),
                                  bg=COLORS['bg_input'], fg=COLORS['text_primary'], insertbackground=COLORS['text_primary'], relief='flat', bd=5)
        self.entry_msg.pack(side='left', fill='both', expand=True, padx=5, pady=15)
        self.entry_msg.bind('<Return>', lambda e: self.send_message())
        self.entry_msg.focus()
        
        tk.Button(input_frame, text="Send", command=self.send_message,
                  bg=COLORS['accent_primary'], fg='white', relief='flat', font=('Segoe UI', 10, 'bold'), padx=20).pack(side='right', padx=10, pady=15)
        
        # Messages area
        msg_canvas = tk.Canvas(self.chat_area, bg=COLORS['bg_main'], highlightthickness=0)
        msg_scrollbar = ttk.Scrollbar(self.chat_area, orient='vertical', command=msg_canvas.yview)
        self.msg_container = tk.Frame(msg_canvas, bg=COLORS['bg_main'])
        
        self.msg_container.bind('<Configure>', lambda e: msg_canvas.configure(scrollregion=msg_canvas.bbox('all')))
        msg_canvas.create_window((0, 0), window=self.msg_container, anchor='nw')
        msg_canvas.configure(yscrollcommand=msg_scrollbar.set)
        
        msg_canvas.pack(side='left', fill='both', expand=True)
        msg_scrollbar.pack(side='right', fill='y')
        
        self.msg_canvas = msg_canvas
        
        # Load history
        if not is_group:
            send_json(self.sock, {'type': 'req_history', 'with': target})
        
        # Display cached messages
        if target in self.chat_history:
            for msg in self.chat_history[target]:
                self.display_message(msg)
    
    def display_message(self, msg):
        """Display message bubble"""
        sender = msg.get('sender')
        content = msg.get('content')
        msg_type = msg.get('type', 'text')
        
        is_me = sender == self.username or sender == 'Me'
        
        # Wrapper frame for the whole message line
        wrapper = tk.Frame(self.msg_container, bg=COLORS['bg_main'])
        wrapper.pack(fill='x', padx=15, pady=5)
        
        # Colors
        bubble_color = COLORS['bubble_me'] if is_me else COLORS['bubble_other']
        text_color = 'white' if is_me else COLORS['text_primary']
        
        # Font setup
        msg_font = font.Font(family="Segoe UI", size=11)
        
        # Measure text size
        max_width = 450
        
        # Helper to create bubble
        def draw_bubble(parent_frame):
            if msg_type == 'text':
                # Calculate dimensions
                lines = []
                words = content.split(' ')
                current_line = []
                
                for word in words:
                    current_line.append(word)
                    if msg_font.measure(' '.join(current_line)) > max_width:
                        current_line.pop()
                        lines.append(' '.join(current_line))
                        current_line = [word]
                lines.append(' '.join(current_line))
                
                text_to_draw = '\n'.join(lines)
                
                # Approximate dimensions
                text_width = 0
                for line in lines:
                    w = msg_font.measure(line)
                    if w > text_width: text_width = w
                
                text_height = len(lines) * (msg_font.metrics("linespace")) + 10
                
                width = text_width + 30
                height = text_height + 20
                
                # Canvas
                c = tk.Canvas(parent_frame, width=width, height=height, bg=COLORS['bg_main'], highlightthickness=0)
                c.pack()
                
                # Draw shape
                draw_rounded_rectangle(c, 5, 5, width-5, height-5, radius=15, fill=bubble_color, outline="")
                
                # Draw text
                c.create_text(width/2, height/2, text=text_to_draw, fill=text_color, font=msg_font)

            elif msg_type in ['file', 'voice']:
                width = 250
                height = 50
                c = tk.Canvas(parent_frame, width=width, height=height, bg=COLORS['bg_main'], highlightthickness=0)
                c.pack()
                draw_rounded_rectangle(c, 5, 5, width-5, height-5, radius=15, fill=bubble_color, outline="")
                c.create_text(width/2, height/2, text=content, fill=text_color, font=msg_font)
                
                # If file/voice, add button below or near (using pack inside parent_frame but outside canvas)
                if msg.get('filepath'):
                    btn = tk.Button(parent_frame, text="📂 Open", command=lambda: self.open_file(msg['filepath']),
                             bg=COLORS['accent_secondary'], fg='white', relief='flat', font=('Arial', 8))
                    btn.pack(pady=2)

        # Alignment Logic
        if is_me:
            # Right aligned
            bubble_container = tk.Frame(wrapper, bg=COLORS['bg_main'])
            bubble_container.pack(side='right')
            draw_bubble(bubble_container)
        else:
            # Left aligned
            # Label for sender name in groups
            if self.is_group_chat:
                tk.Label(wrapper, text=sender, font=('Segoe UI', 8, 'bold'), fg=COLORS['text_secondary'], bg=COLORS['bg_main']).pack(anchor='w', padx=5)
            
            bubble_container = tk.Frame(wrapper, bg=COLORS['bg_main'])
            bubble_container.pack(side='left')
            draw_bubble(bubble_container)

        # Auto-scroll
        self.msg_canvas.update_idletasks()
        self.msg_canvas.yview_moveto(1.0)
    
    def send_message(self):
        """Send text message"""
        if not self.active_chat:
            return
        
        text = self.entry_msg.get().strip()
        if not text:
            return
        
        if self.is_group_chat:
            send_json(self.sock, {'type': 'group_msg', 'room_name': self.active_chat, 'content': text})
        else:
            send_json(self.sock, {'type': 'private', 'to': self.active_chat, 'content': text})
        
        self.entry_msg.delete(0, 'end')
        
        msg = {'sender': 'Me', 'content': text, 'type': 'text'}
        self.save_message(self.active_chat, msg)
        self.display_message(msg)
    
    def send_file(self):
        """Send file"""
        if not self.active_chat:
            return
        
        filepath = filedialog.askopenfilename()
        if not filepath:
            return
        
        if os.path.getsize(filepath) > 5 * 1024 * 1024:
            messagebox.showerror("Error", "File too large (max 5MB)")
            return
        
        with open(filepath, 'rb') as f:
            content = base64.b64encode(f.read()).decode()
        
        filename = os.path.basename(filepath)
        
        if self.is_group_chat:
            send_json(self.sock, {'type': 'group_file', 'room_name': self.active_chat,
                                 'filename': filename, 'content': content})
        else:
            send_json(self.sock, {'type': 'file', 'to': self.active_chat,
                                 'filename': filename, 'content': content})
        
        msg = {'sender': 'Me', 'content': f"📎 {filename}", 'type': 'file', 'filepath': filepath}
        self.save_message(self.active_chat, msg)
        self.display_message(msg)
    
    def create_group(self):
        """Create new group"""
        name = simpledialog.askstring("Create Group", "Enter group name:")
        if not name:
            return
        
        pin = simpledialog.askstring("Create Group", "Set PIN (password):", show='*')
        if not pin:
            return
        
        send_json(self.sock, {'type': 'group_create', 'room_name': name, 'pin': pin})
    
    def join_group(self, group_name):
        """Join group"""
        pin = simpledialog.askstring("Join Group", f"Enter PIN for '{group_name}':", show='*')
        if pin:
            send_json(self.sock, {'type': 'group_join', 'room_name': group_name, 'pin': pin})
    
    def leave_group(self, group_name):
        """Leave group"""
        if messagebox.askyesno("Leave Group", f"Leave '{group_name}'?"):
            send_json(self.sock, {'type': 'group_leave', 'room_name': group_name})
            self.active_chat = None
            for widget in self.chat_area.winfo_children():
                widget.destroy()
            self.placeholder = tk.Label(self.chat_area, text="Select a user or group to start chatting",
                                       font=('Segoe UI', 14), fg=COLORS['text_secondary'], bg=COLORS['bg_main'])
            self.placeholder.place(relx=0.5, rely=0.5, anchor='center')

    def add_user_to_group(self, group_name):
        """Add user to group by creator"""
        target = simpledialog.askstring("Add User", "Enter username to add:")
        if target:
            send_json(self.sock, {'type': 'group_add_user', 'room_name': group_name, 'target_user': target})
    
    def initiate_call(self, target, mode):
        """Initiate 1-to-1 call"""
        if not AUDIO_AVAILABLE:
            messagebox.showwarning("Warning", "Audio not available")
            return
        
        if mode == 'video' and not VIDEO_AVAILABLE:
            messagebox.showwarning("Warning", "Video not available - starting audio call")
            mode = 'audio'
        
        send_json(self.sock, {'type': 'call', 'to': target, 'mode': mode})
        self.show_calling_window(target, mode)
    
    def show_calling_window(self, target, mode):
        """Show calling window"""
        self.call_win = tk.Toplevel(self)
        self.call_win.title("Calling...")
        self.call_win.geometry("300x150")
        self.call_win.configure(bg=COLORS['bg_main'])
        tk.Label(self.call_win, text=f"Calling {target}...", font=('Segoe UI', 14),
                fg=COLORS['text_primary'], bg=COLORS['bg_main']).pack(expand=True)
    
    def show_incoming_call(self, caller, mode):
        """Show incoming call dialog"""
        win = tk.Toplevel(self)
        win.title("Incoming Call")
        win.geometry("350x200")
        win.configure(bg=COLORS['bg_main'])
        
        tk.Label(win, text=f"{mode.upper()} Call", font=('Segoe UI', 16, 'bold'),
                fg=COLORS['accent_primary'], bg=COLORS['bg_main']).pack(pady=10)
        tk.Label(win, text=f"from {caller}", font=('Segoe UI', 14),
                fg=COLORS['text_primary'], bg=COLORS['bg_main']).pack(pady=5)
        
        btn_frame = tk.Frame(win, bg=COLORS['bg_main'])
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="Accept", font=('Segoe UI', 11, 'bold'),
                 bg=COLORS['accent_secondary'], fg='white', relief='flat', padx=30, pady=10,
                 command=lambda: [win.destroy(), self.accept_call(caller, mode)]).pack(side='left', padx=10)
        tk.Button(btn_frame, text="Reject", font=('Segoe UI', 11, 'bold'),
                 bg=COLORS['accent_danger'], fg='white', relief='flat', padx=30, pady=10,
                 command=lambda: [win.destroy(), send_json(self.sock, {'type': 'call_reject', 'to': caller})]).pack(side='left', padx=10)
    
    def accept_call(self, caller, mode):
        """Accept incoming call"""
        send_json(self.sock, {'type': 'call_accept', 'to': caller, 'mode': mode})
        self.start_call_session(caller, mode, is_group=False)
    
    def start_call_session(self, target, mode, is_group=False):
        """Start call session"""
        print(f"[CALL] Starting {mode} call with {target} (Group: {is_group})")
        self.call_active = True
        self.call_target = target
        self.call_mode = mode
        self.call_is_group = is_group
        
        if hasattr(self, 'call_win') and self.call_win.winfo_exists():
            self.call_win.destroy()
        
        self.call_win = tk.Toplevel(self)
        self.call_win.title(f"{mode.title()} Call - {target}")
        
        if mode == 'video':
            self.call_win.geometry("500x450")
        else:
            self.call_win.geometry("400x300")
        
        self.call_win.configure(bg=COLORS['bg_main'])
        self.call_win.protocol("WM_DELETE_WINDOW", self.end_call)
        
        tk.Label(self.call_win, text=f"Connected to {target}", font=('Segoe UI', 12),
                fg=COLORS['accent_secondary'], bg=COLORS['bg_main']).pack(pady=10)
        
        # Video display for video calls
        if mode == 'video' and VIDEO_AVAILABLE:
            self.video_label = tk.Label(self.call_win, bg='black', width=480, height=360)
            self.video_label.pack(padx=10, pady=10)
        
        tk.Button(self.call_win, text="End Call", font=('Segoe UI', 12, 'bold'),
                 bg=COLORS['accent_danger'], fg='white', relief='flat', padx=40, pady=12,
                 command=self.end_call).pack(pady=10)
        
        # Setup audio
        if AUDIO_AVAILABLE:
            try:
                self.p = pyaudio.PyAudio()
                self.stream_in = self.p.open(format=pyaudio.paInt16, channels=1, rate=24000,
                                            input=True, frames_per_buffer=1024)
                self.stream_out = self.p.open(format=pyaudio.paInt16, channels=1, rate=24000,
                                             output=True, frames_per_buffer=1024)
                
                self.udp_audio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # IMPORTANT: Send REG packet to the correctly connected server IP
                self.udp_audio.sendto(f"REG:{self.username}".encode(), (self.server_ip, UDP_AUDIO_PORT))
                
                threading.Thread(target=self._audio_tx, daemon=True).start()
                threading.Thread(target=self._audio_rx, daemon=True).start()
                print("[CALL] Audio streams started")
            except Exception as e:
                print(f"[ERROR] Audio setup failed: {e}")
                messagebox.showerror("Error", f"Audio failed: {e}")
                self.end_call()
                return
        
        # Setup video
        if mode == 'video' and VIDEO_AVAILABLE:
            try:
                self.udp_video = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.udp_video.sendto(f"REG:{self.username}".encode(), (self.server_ip, UDP_VIDEO_PORT))
                
                self.cap = cv2.VideoCapture(0)
                if not self.cap.isOpened():
                    raise Exception("Cannot open camera")
                
                threading.Thread(target=self._video_tx, daemon=True).start()
                threading.Thread(target=self._video_rx, daemon=True).start()
                print("[CALL] Video streams started")
            except Exception as e:
                print(f"[ERROR] Video setup failed: {e}")
                messagebox.showwarning("Warning", f"Video failed: {e}\nContinuing with audio only")
    
    def _audio_tx(self):
        """Transmit audio"""
        while self.call_active:
            try:
                # Type guard for call_target
                if not self.call_target:
                    break
                
                data = self.stream_in.read(1024, exception_on_overflow=False)
                # Prefix changes based on Group Call (G) or Private Call (A)
                prefix = b'G' if self.call_is_group else b'A'
                packet = prefix + self.call_target.encode() + b'\0' + data
                self.udp_audio.sendto(packet, (self.server_ip, UDP_AUDIO_PORT))
            except:
                break
    
    def _audio_rx(self):
        """Receive audio"""
        while self.call_active:
            try:
                data, _ = self.udp_audio.recvfrom(4096)
                self.stream_out.write(data)
            except:
                break
    
    def _video_tx(self):
        """Transmit video"""
        while self.call_active:
            try:
                # Type guard for call_target
                if not self.call_target:
                    break
                
                ret, frame = self.cap.read()
                if not ret:
                    continue
                
                # Resize and compress
                frame = cv2.resize(frame, (320, 240))
                _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                
                # Prefix changes based on Group Call (H) or Private Call (V)
                prefix = b'H' if self.call_is_group else b'V'
                packet = prefix + self.call_target.encode() + b'\0' + buffer.tobytes()
                
                if len(packet) < 60000:
                    self.udp_video.sendto(packet, (self.server_ip, UDP_VIDEO_PORT))
                
                time.sleep(0.033)  # ~30 FPS
            except Exception as e:
                print(f"[ERROR] Video TX: {e}")
                break
    
    def _video_rx(self):
        """Receive video"""
        while self.call_active:
            try:
                data, _ = self.udp_video.recvfrom(60000)
                
                # Decode and display
                image = Image.open(io.BytesIO(data))
                photo = ImageTk.PhotoImage(image)
                
                if self.call_active and hasattr(self, 'video_label'):
                    self.after(0, lambda p=photo: self._update_video(p))
            except:
                pass
    
    def _update_video(self, photo):
        """Update video label (must run on main thread)"""
        try:
            if hasattr(self, 'video_label') and self.video_label.winfo_exists():
                self.video_label.configure(image=photo)
                self.video_label.image = photo  # type: ignore
        except:
            pass
    
    def end_call(self):
        """End call"""
        print("[CALL] Ending call")
        self.call_active = False
        try:
            self.call_win.destroy()
        except:
            pass
        try:
            self.stream_in.stop_stream()
            self.stream_in.close()
            self.stream_out.stop_stream()
            self.stream_out.close()
            self.p.terminate()
            self.udp_audio.close()
        except:
            pass
        try:
            if hasattr(self, 'cap'):
                self.cap.release()
            if hasattr(self, 'udp_video'):
                self.udp_video.close()
        except:
            pass
    
    def initiate_group_call(self, room, mode):
        """Initiate group call"""
        send_json(self.sock, {'type': 'group_call', 'room_name': room, 'mode': mode})
        # The initiator auto-joins the call they started
        self.start_call_session(room, mode, is_group=True)
    
    def save_message(self, chat, msg):
        """Save message to history"""
        if chat not in self.chat_history:
            self.chat_history[chat] = []
        self.chat_history[chat].append(msg)
    
    def open_file(self, filepath):
        """Open file"""
        try:
            if sys.platform == 'win32':
                os.startfile(filepath)
            elif sys.platform == 'darwin':
                os.system(f'open "{filepath}"')
            else:
                os.system(f'xdg-open "{filepath}"')
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}")
    
    def message_listener(self):
        """Listen for incoming messages"""
        while self.running:
            try:
                msg = receive_json(self.sock)
                if not msg:
                    break
                self.after(0, self.handle_message, msg)
            except:
                break
    
    def handle_message(self, msg):
        """Handle incoming message"""
        msg_type = msg.get('type')
        
        if msg_type == 'list':
            self.update_users_list(msg['users'])
        
        elif msg_type == 'all_groups_list':
            self.update_all_groups_list(msg['groups'])
        
        elif msg_type == 'my_groups_list':
            self.update_my_groups_list(msg['groups'])
        
        elif msg_type == 'history':
            partner = msg['with']
            
            # Clear existing history to prevent duplicates
            self.chat_history[partner] = []
            
            # If active, clear UI to prevent duplicates
            if self.active_chat == partner:
                for widget in self.msg_container.winfo_children():
                    widget.destroy()
            
            for item in msg['data']:
                self.save_message(partner, item)
                if self.active_chat == partner:
                    self.display_message(item)
        
        elif msg_type == 'private':
            sender = msg['from']
            content = msg['content']
            message = {'sender': sender, 'content': content, 'type': 'text'}
            self.save_message(sender, message)
            if self.active_chat == sender:
                self.display_message(message)
        
        elif msg_type == 'file':
            sender = msg['from']
            filename = msg['filename']
            content = msg['content']
            
            os.makedirs("DOWNLOADS", exist_ok=True)
            filepath = os.path.join("DOWNLOADS", filename)
            
            # Only save file once
            if not os.path.exists(filepath):
                with open(filepath, 'wb') as f:
                    f.write(base64.b64decode(content))
            
            message = {'sender': sender, 'content': f"📎 {filename}", 'type': 'file', 'filepath': filepath}
            self.save_message(sender, message)
            if self.active_chat == sender:
                self.display_message(message)
        
        elif msg_type == 'voice_msg':
            sender = msg['from']
            content = msg['content']
            duration = msg.get('duration', 0)
            
            os.makedirs("DOWNLOADS", exist_ok=True)
            filepath = os.path.join("DOWNLOADS", f"voice_{sender}_{int(time.time())}.wav")
            
            # Only save file once
            if not os.path.exists(filepath):
                with open(filepath, 'wb') as f:
                    f.write(base64.b64decode(content))
            
            message = {'sender': sender, 'content': f"🎤 Voice ({duration:.1f}s)",
                      'type': 'voice', 'filepath': filepath}
            self.save_message(sender, message)
            if self.active_chat == sender:
                self.display_message(message)
        
        elif msg_type == 'group_msg':
            room = msg['room_name']
            sender = msg['from']
            content = msg['content']
            message = {'sender': sender, 'content': content, 'type': 'text'}
            self.save_message(room, message)
            if self.active_chat == room:
                self.display_message(message)
        
        elif msg_type == 'group_file':
            room = msg['room_name']
            sender = msg['from']
            filename = msg['filename']
            content = msg['content']
            
            os.makedirs("DOWNLOADS", exist_ok=True)
            filepath = os.path.join("DOWNLOADS", f"{room}_{filename}")
            
            # Only save file once
            if not os.path.exists(filepath):
                with open(filepath, 'wb') as f:
                    f.write(base64.b64decode(content))
            
            message = {'sender': sender, 'content': f"📎 {filename}", 'type': 'file', 'filepath': filepath}
            self.save_message(room, message)
            if self.active_chat == room:
                self.display_message(message)
        
        elif msg_type == 'text':
            # System message - only show once
            content = msg.get('content', '')
            if content:
                print(f"[SYSTEM] {content}")
                messagebox.showinfo("System", content)
        
        elif msg_type == 'call':
            self.show_incoming_call(msg['from'], msg.get('mode', 'audio'))
        
        elif msg_type == 'call_accept':
            self.start_call_session(msg['from'], msg['mode'], is_group=False)
        
        elif msg_type == 'group_call':
            # Everyone gets notified of the group call
            # For simplicity, we can show a join prompt or just a notification
            if messagebox.askyesno("Group Call", f"Join call in '{msg['room_name']}'?"):
                send_json(self.sock, {'type': 'group_call_accept', 'room_name': msg['room_name']})
                self.start_call_session(msg['room_name'], msg['mode'], is_group=True)

        elif msg_type == 'call_reject':
            print("[CALL] Call rejected")
            messagebox.showinfo("Call", "Call rejected")
            if hasattr(self, 'call_win'):
                self.call_win.destroy()
    
    def update_users_list(self, users):
        """Update users list"""
        for widget in self.users_list.winfo_children():
            widget.destroy()
        
        for user in users:
            if user['username'] != self.username:
                frame = tk.Frame(self.users_list, bg=COLORS['bg_panel'])
                frame.pack(fill='x', pady=1)
                
                color = COLORS['online'] if user['status'] == 'online' else COLORS['offline']
                tk.Label(frame, text="●", fg=color, bg=COLORS['bg_panel'], font=('Arial', 10)).pack(side='left', padx=8)
                
                tk.Button(frame, text=user['username'], command=lambda u=user['username']: self.open_chat(u, False),
                         bg=COLORS['bg_panel'], fg=COLORS['text_primary'], font=('Segoe UI', 10), relief='flat', anchor='w',
                         activebackground=COLORS['bg_input']).pack(side='left', fill='x', expand=True)
    
    def update_my_groups_list(self, groups):
        """Update my groups list"""
        for widget in self.my_groups_list.winfo_children():
            widget.destroy()
        
        for group_data in groups:
            # FIX: Handle dictionary format
            if isinstance(group_data, dict):
                group = group_data['name']
                creator = group_data['creator']
                self.group_creators[group] = creator
            else:
                group = group_data # Fallback for old format
                self.group_creators[group] = "Unknown"

            tk.Button(self.my_groups_list, text=f"# {group}", command=lambda g=group: self.open_chat(g, True),
                     bg=COLORS['bg_panel'], fg=COLORS['text_primary'], font=('Segoe UI', 10, 'bold'), relief='flat', anchor='w',
                     activebackground=COLORS['bg_input']).pack(fill='x', pady=2, padx=5)
    
    def update_all_groups_list(self, groups):
        """Update all groups list"""
        for widget in self.all_groups_list.winfo_children():
            widget.destroy()
        
        for group in groups:
            frame = tk.Frame(self.all_groups_list, bg=COLORS['bg_panel'])
            frame.pack(fill='x', pady=2, padx=5)
            
            tk.Label(frame, text=group, fg=COLORS['text_primary'], bg=COLORS['bg_panel'], font=('Segoe UI', 10)).pack(side='left', padx=5)
            tk.Button(frame, text="Join", command=lambda g=group: self.join_group(g),
                     bg=COLORS['accent_primary'], fg='white', relief='flat', font=('Segoe UI', 8), padx=8).pack(side='right')
    
    def on_close(self):
        """Handle window close"""
        self.running = False
        self.call_active = False
        if self.sock:
            self.sock.close()
        self.destroy()
        sys.exit()

if __name__ == "__main__":
    app = ChatClient()
    app.mainloop()