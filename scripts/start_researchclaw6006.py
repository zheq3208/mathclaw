import os
import signal
import subprocess
import time
from pathlib import Path

repo = Path('/root/autodl-tmp/mathclaw')
runtime_dir = repo / '.runtime'
runtime_dir.mkdir(parents=True, exist_ok=True)
pid_path = runtime_dir / 'researchclaw6006.pid'
log_path = runtime_dir / 'researchclaw6006-live.log'

for pid_file in (pid_path, Path('/tmp/researchclaw6006.pid')):
    if pid_file.exists():
        try:
            os.kill(int(pid_file.read_text().strip()), signal.SIGTERM)
            time.sleep(1)
        except Exception:
            pass
for cmd in (
    "pkill -f '/root/miniconda3/bin/researchclaw app --host 0.0.0.0 --port 6006' >/dev/null 2>&1 || true",
    "pkill -f '/root/miniconda3/bin/researchclaw app --host 127.0.0.1 --port 6006' >/dev/null 2>&1 || true",
):
    subprocess.run(cmd, shell=True, check=False)

env = os.environ.copy()
env['RESEARCHCLAW_WORKING_DIR'] = str(repo / '.researchclaw')
env['RESEARCHCLAW_SECRET_DIR'] = str(repo / '.researchclaw.secret')
proc = subprocess.Popen(
    ['/root/miniconda3/bin/researchclaw', 'app', '--host', '0.0.0.0', '--port', '6006'],
    cwd=str(repo),
    env=env,
    stdout=open(log_path, 'ab'),
    stderr=subprocess.STDOUT,
    start_new_session=True,
)
pid_path.write_text(str(proc.pid), encoding='utf-8')
print(proc.pid)
