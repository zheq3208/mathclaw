import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
runtime_dir = repo / ".runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)
pid_path = runtime_dir / "mathclaw6006.pid"
log_path = runtime_dir / "mathclaw6006-live.log"

mathclaw_bin = os.environ.get("MATHCLAW_BIN") or shutil.which("mathclaw")
if not mathclaw_bin and Path("/root/miniconda3/bin/mathclaw").exists():
    mathclaw_bin = "/root/miniconda3/bin/mathclaw"
if not mathclaw_bin:
    raise SystemExit(
        "mathclaw command not found. Run `pip install -e .` first or set MATHCLAW_BIN."
    )

for pid_file in (pid_path, Path("/tmp/mathclaw6006.pid")):
    if pid_file.exists():
        try:
            os.kill(int(pid_file.read_text().strip()), signal.SIGTERM)
            time.sleep(1)
        except Exception:
            pass

devnull = subprocess.DEVNULL
for pattern in (
    "mathclaw app --host 127.0.0.1 --port 6006",
    "mathclaw app --host 0.0.0.0 --port 6006",
    "researchclaw app --host 127.0.0.1 --port 6006",
    "researchclaw app --host 0.0.0.0 --port 6006",
):
    subprocess.run(["pkill", "-f", pattern], check=False, stdout=devnull, stderr=devnull)

env = os.environ.copy()
env.setdefault("MATHCLAW_WORKING_DIR", str(repo / ".mathclaw"))
env.setdefault("MATHCLAW_SECRET_DIR", str(repo / ".mathclaw.secret"))
Path(env["MATHCLAW_WORKING_DIR"]).mkdir(parents=True, exist_ok=True)
Path(env["MATHCLAW_SECRET_DIR"]).mkdir(parents=True, exist_ok=True)

with open(log_path, "ab") as log_fp:
    proc = subprocess.Popen(
        [mathclaw_bin, "app", "--host", "127.0.0.1", "--port", "6006"],
        cwd=str(repo),
        env=env,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

pid_path.write_text(str(proc.pid), encoding="utf-8")
print(proc.pid)
