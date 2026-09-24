"""Start an isolated GUI Chrome in Docker for the runner's --cdp-url mode.

The CDP port is published only on the host loopback interface. The browser
profile lives inside this disposable container and is not a host Chrome profile.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


HERE = Path(__file__).resolve().parent
IMAGE = "persona-cua-browser:chrome153"
NAME = "persona-cua-browser"
LABEL = "persona-cua.browser-probe=1"


def docker_executable() -> str:
    found = shutil.which("docker")
    if found:
        return found
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        candidate = Path(local) / "Programs/DockerDesktop/resources/bin/docker.exe"
        if candidate.is_file():
            return str(candidate)
    raise SystemExit("Docker CLI not found; install/start Docker Desktop first")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9333)
    parser.add_argument("--stop", action="store_true",
                        help="stop only the labeled browser container")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")

    docker = docker_executable()
    env = os.environ.copy()
    # A per-user Docker Desktop install may not be on PATH. Its credential
    # helper lives next to docker.exe; expose it to this subprocess only.
    env["PATH"] = str(Path(docker).parent) + os.pathsep + env.get("PATH", "")

    def run(*argv: str, capture: bool = False) -> str:
        result = subprocess.run([docker, *argv], check=True, env=env,
                                text=True, capture_output=capture)
        return result.stdout.strip() if capture else ""

    try:
        run("info", "--format", "{{.OSType}}", capture=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit("Docker engine is not running; run 'docker desktop start' first") from exc

    existing = run("ps", "-a", "--filter", f"name=^{NAME}$",
                   "--format", "{{.Names}}", capture=True)
    if existing:
        label = run("inspect", "-f", "{{index .Config.Labels "
                    "\"persona-cua.browser-probe\"}}", NAME, capture=True)
        if label != "1":
            raise SystemExit(f"container {NAME!r} exists but is not owned by this script")
        if args.stop:
            run("stop", NAME)
            print(f"Stopped {NAME}; the disposable browser profile was removed.")
            return
        raise SystemExit(f"{NAME} already exists; use --stop before starting a new one")
    if args.stop:
        print(f"{NAME} is not running")
        return

    run("build", "-t", IMAGE, "-f", str(HERE / "docker_browser/Dockerfile"),
        str(HERE / "docker_browser"))
    run("run", "--rm", "-d", "--name", NAME, "--label", LABEL,
        "--shm-size=2g", "-p", f"127.0.0.1:{args.port}:9333", IMAGE)
    run("exec", "-d", NAME, "google-chrome", "--no-sandbox",
        "--no-first-run", "--user-data-dir=/tmp/persona-gui-chrome",
        "--remote-debugging-port=9223", "--new-window",
        "https://www.google.com/")
    run("exec", "-d", NAME, "socat",
        "TCP-LISTEN:9333,bind=0.0.0.0,reuseaddr,fork", "TCP:127.0.0.1:9223")

    endpoint = f"http://127.0.0.1:{args.port}"
    for _ in range(30):
        try:
            with urlopen(endpoint + "/json/version", timeout=2) as response:
                if json.load(response).get("webSocketDebuggerUrl"):
                    print(f"Chrome ready. Pass --cdp-url {endpoint} to odyssey/run.py")
                    return
        except (OSError, ValueError):
            time.sleep(1)
    raise SystemExit(f"Chrome did not become ready at {endpoint}; inspect Docker logs")


if __name__ == "__main__":
    main()
