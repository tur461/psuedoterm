import os
import select
import uuid
import sys
from ctypes import cdll, c_int, c_char_p
from flask import Flask, request, jsonify

app = Flask(__name__)

sessions = {}

# Load libc for system calls
libc = cdll.LoadLibrary("libc.so.6")

# Constants for system calls
O_RDWR = 2
S_IRUSR = 0o400
S_IWUSR = 0o200

def set_raw_mode(fd):
    """Set terminal to raw mode using system calls"""
    termios_lib = cdll.LoadLibrary("libc.so.6")
    termios_lib.tcsetattr.argtypes = [c_int, c_int, c_int]
    termios_lib.tcgetattr.argtypes = [c_int]
    attrs = termios_lib.tcgetattr(fd)
    termios_lib.tcsetattr(fd, 1, attrs)

def fork_process():
    # fork a new process
    pid = libc.fork()
    if pid < 0:
        raise OSError("Fork failed")
    return pid

def exec_command(command):
    # Executes a command in the child process
    libc.execvp(c_char_p(command[0]), (c_char_p(arg) for arg in command))

@app.route("/create_session", methods=["POST"])
def create_session():
    session_id = str(uuid.uuid4())
    
    pid = fork_process()

    if pid == 0:  # Child process
        # Execute shell in child process (command passed as a list)
        exec_command(["/bin/bash"])
        sys.exit(0)
    else:  # Parent process
        # Parent process will not have control over terminal directly
        fd_master = os.open("/dev/tty", O_RDWR)
        sessions[session_id] = fd_master
        return jsonify(session_id), 201

@app.route("/execute_command", methods=["POST"])
def execute_command():
    session_id = request.json.get("session_id")
    command = request.json.get("command")

    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    fd_master = sessions[session_id]

    # Write the command to the terminal
    os.write(fd_master, (command + "\n").encode())

    output = b""
    while True:
        r, _, _ = select.select([fd_master], [], [], 0.1)
        if fd_master in r:
            try:
                data = os.read(fd_master, 1024)
                output += data
                if not data or data.endswith(b"$ "):
                    break
            except OSError:
                break

    return jsonify({"output": output.decode(errors="ignore").strip()})

@app.route("/close_session", methods=["POST"])
def close_session():
    session_id = request.json.get("session_id")

    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    fd_master = sessions.pop(session_id)
    os.close(fd_master)
    return jsonify({"message": "Session closed"}), 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
