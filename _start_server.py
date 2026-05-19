import subprocess, sys, os, time

script = os.path.join(os.path.dirname(__file__), 'app.py')
proc = subprocess.Popen(
    [sys.executable, script],
    cwd=os.path.dirname(__file__),
    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)
pid_file = os.path.join(os.path.dirname(__file__), 'server_pid.txt')
with open(pid_file, 'w') as f:
    f.write(str(proc.pid))
print(f'Server started (PID: {proc.pid})')
