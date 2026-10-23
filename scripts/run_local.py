"""Start the local workspace; Ctrl+C stops only the API/UI processes started here."""

import argparse
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, help="Optionally import annual SMARD exports first"
    )
    args = parser.parse_args()
    for port in (18000, 18501):
        with socket.socket() as connection:
            if connection.connect_ex(("127.0.0.1", port)) == 0:
                raise SystemExit(f"Port {port} is already in use. Stop the existing process first.")
    subprocess.run(
        ["docker", "compose", "up", "-d", "--wait", "--pull", "never", "db"], cwd=ROOT, check=True
    )
    subprocess.run([sys.executable, "-m", "energy_ops", "init-db"], cwd=ROOT, check=True)
    if args.data_dir:
        files = sorted(args.data_dir.resolve().glob("Actual_generation_*_Quarterhour.csv"))
        if not files:
            raise SystemExit(f"No annual exports found in {args.data_dir}")
        for path in files:
            match = re.fullmatch(r"Actual_generation_(\d{12})_(\d{12})_Quarterhour.csv", path.name)
            if not match:
                raise SystemExit(f"Unrecognized export filename: {path.name}")
            start, end = [datetime.strptime(v, "%Y%m%d%H%M") for v in match.groups()]
            if any(dt.hour or dt.minute for dt in (start, end)):
                raise SystemExit("Local launcher imports require midnight period boundaries")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "energy_ops",
                    "import-smard",
                    str(path),
                    "--start-date",
                    start.date().isoformat(),
                    "--end-date",
                    end.date().isoformat(),
                ],
                cwd=ROOT,
                check=True,
            )
    logs = ROOT / ".local" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    processes = []
    handles = []
    try:
        for name, command in (
            (
                "api",
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "energy_ops.api:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "18000",
                ],
            ),
            (
                "dashboard",
                [sys.executable, "-m", "streamlit", "run", "src/energy_ops/dashboard.py"],
            ),
        ):
            handle = (logs / f"{name}.log").open("a")
            handles.append(handle)
            processes.append(
                subprocess.Popen(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
            )
        for url in ("http://127.0.0.1:18000/health/ready", "http://127.0.0.1:18501/_stcore/health"):
            for _ in range(60):
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError(f"A service exited. Check {logs}")
                try:
                    if requests.get(url, timeout=2).status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(0.5)
            else:
                raise RuntimeError(f"Service startup timed out. Check {logs}")
        print("Dashboard: http://127.0.0.1:18501", flush=True)
        print("API docs:  http://127.0.0.1:18000/docs", flush=True)
        print("Press Ctrl+C to stop the API and dashboard. PostgreSQL data persists.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        for handle in handles:
            handle.close()


if __name__ == "__main__":
    main()
