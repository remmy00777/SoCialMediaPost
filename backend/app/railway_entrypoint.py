from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence


def start_process(command: Sequence[str]) -> subprocess.Popen:
    print(f"Starting: {' '.join(command)}", flush=True)
    return subprocess.Popen(list(command))


def stop_processes(processes: list[subprocess.Popen]) -> None:
    for process in processes:
        if process.poll() is None:
            process.terminate()

    deadline = time.time() + 15

    while time.time() < deadline:
        if all(process.poll() is not None for process in processes):
            return
        time.sleep(0.25)

    for process in processes:
        if process.poll() is None:
            process.kill()


def main() -> int:
    port = os.getenv("PORT", "8765")
    celery_enabled = os.getenv("CELERY_ENABLED", "true").lower() == "true"

    print("Running database migrations...", flush=True)
    subprocess.run(["alembic", "upgrade", "head"], check=True)

    processes: list[subprocess.Popen] = []

    processes.append(
        start_process(
            [
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                port,
                "--proxy-headers",
                "--forwarded-allow-ips",
                "*",
            ]
        )
    )

    if celery_enabled:
        processes.append(
            start_process(
                [
                    "celery",
                    "-A",
                    "app.worker.celery_app",
                    "worker",
                    "--loglevel=INFO",
                    "--concurrency=2",
                    "--max-tasks-per-child=100",
                ]
            )
        )

        processes.append(
            start_process(
                [
                    "celery",
                    "-A",
                    "app.worker.celery_app",
                    "beat",
                    "--loglevel=INFO",
                    "--schedule=/data/storage/celerybeat-schedule",
                ]
            )
        )

    def shutdown(signum: int, _frame: object) -> None:
        print(f"Received signal {signum}, shutting down...", flush=True)
        stop_processes(processes)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        while True:
            for process in processes:
                return_code = process.poll()

                if return_code is not None:
                    print(
                        f"Process {process.pid} exited with code {return_code}.",
                        flush=True,
                    )
                    stop_processes(processes)
                    return return_code or 1

            time.sleep(2)
    finally:
        stop_processes(processes)


if __name__ == "__main__":
    sys.exit(main())
