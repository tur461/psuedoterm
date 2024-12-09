import os
import pty
import select
import termios
import tty
import uuid
from flask import Flask, request, jsonify

app = Flask(__name__)

sessions = {}

def set_raw_mode(fd):
    attrs = termios.tcgetattr(fd)
    tty.setraw(fd)
    termios.tcsetattr(fd, termios.TCSADRAIN, attrs)

@app.route("/create_session", methods=["POST"])
def create_session():
    session_id = str(uuid.uuid4())
    pid, master_fd = pty.fork()

    if pid == 0:  # Child process
        os.execv("/bin/bash", ["/bin/bash"])
    else:  # Parent process
        set_raw_mode(master_fd)
        sessions[session_id] = master_fd
        return jsonify(session_id), 201

@app.route("/execute_command", methods=["POST"])
def execute_command():
    session_id = request.json.get("session_id")
    command = request.json.get("command")

    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    master_fd = sessions[session_id]

    os.write(master_fd, (command + "\n").encode())

    output = b""
    while True:
        r, _, _ = select.select([master_fd], [], [], 0.1)
        if master_fd in r:
            try:
                data = os.read(master_fd, 1024)
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

    master_fd = sessions.pop(session_id)
    os.close(master_fd)
    return jsonify({"message": "Session closed"}), 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

