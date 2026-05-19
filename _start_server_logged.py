import subprocess, sys, os, time

script = os.path.join(os.path.dirname(__file__), 'app.py')
out = open(os.path.join(os.path.dirname(__file__), 'server_out.log'), 'a', 1)
err = open(os.path.join(os.path.dirname(__file__), 'server_err.log'), 'a', 1)
out.write(f'\n=== Server started at {time.ctime()} ===\n')
err.write(f'\n=== Server started at {time.ctime()} ===\n')
out.flush()
err.flush()

proc = subprocess.Popen(
    [sys.executable, script],
    cwd=os.path.dirname(__file__),
    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
    stdout=out,
    stderr=err,
)
pid_file = os.path.join(os.path.dirname(__file__), 'server_pid.txt')
with open(pid_file, 'w') as f:
    f.write(str(proc.pid))
print(f'Server started (PID: {proc.pid})')
