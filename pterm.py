import os
import pty
import select
import termios
import tty
import subprocess
import uuid
import re
from flask import Flask, request, jsonify

app = Flask(__name__)

sessions = {}

def set_raw_mode(fd):
    attrs = termios.tcgetattr(fd)
    tty.setraw(fd)
    termios.tcsetattr(fd, termios.TCSADRAIN, attrs)

def clean_output(output):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    cleaned = ansi_escape.sub('', output).strip()
    return cleaned.replace('\u0007', '').strip()

@app.route("/new_session", methods=["GET"])
def create_session():
    s_id = str(uuid.uuid4())
    pid, master_fd = pty.fork()

    if pid == 0:
        #print('pid is 0, fallback to /bin/sh')
        os.execv("/bin/sh", ["/bin/sh"]) 
    else: # parent proc
        set_raw_mode(master_fd)
        sessions[s_id] = master_fd
        return jsonify(s_id), 201

def flushPty(mfd):
    while True:
        r, _, _ = select.select([mfd], [], [], 0.1)
        if mfd in r:
            try:
                os.read(mfd, 1024)
            except OSError:
                break
        else:
            break

def readFromPty(mfd):
    output = ""
    while True:
        r, _, _ = select.select([mfd], [], [], 0.1)
        if mfd in r:
            try:
                data = os.read(mfd, 1024).decode()
                output += data
                if not data or data.endswith("$ "):
                    break
            except OSError:
                break
    return output

@app.route("/exec_cmd", methods=["POST"])
def execute_command():
    print('req:', request.json)
    s_id = request.json.get("s_id")
    cmd = request.json.get("cmd")
    sudo_pswd = request.json.get("pswd", None)

    if s_id not in sessions:
        return jsonify("Session not found"), 404

    master_fd = sessions[s_id]
    print('selected MFD:', master_fd)
    
    # flush previous
    flushPty(master_fd)
    
    os.write(master_fd, (cmd + "\n").encode())

    output = readFromPty(master_fd)

    if "password for" in output.lower() and sudo_pswd:
        # send the password if prompted
        os.write(master_fd, (sudo_pswd + "\n").encode())
        output += read_from_pty(master_fd)

    clean = clean_output(output)
    return jsonify(clean)

@app.route("/end_session", methods=["POST"])
def close_session():
    s_id = request.json.get("s_id")

    if s_id not in sessions:
        return jsonify("Session not found"), 404

    master_fd = sessions.pop(s_id)
    os.close(master_fd)
    return jsonify("Session closed"), 200

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

