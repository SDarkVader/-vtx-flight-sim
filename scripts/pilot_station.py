"""VTX local station watchdog: keep one pilot and one live server available.

Existing live server is adopted, not killed. On disappearance, launch a new
server from this checkout; aircraft/session state is NOT fabricated or replayed.
A crash retry is the pilot's separate responsibility. Stop with Ctrl+C.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
LOGS=ROOT/"pilot"
HOST="127.0.0.1"
PORT=8765


def server_alive(url):
    try:
        with urlopen(url+"/api/view",timeout=2) as response:
            return response.status==200
    except (OSError, ValueError):
        return False


def stamp(message):
    print(datetime.now(timezone.utc).isoformat(),message,flush=True)


def supervise(host=HOST,port=PORT,interval=2):
    LOGS.mkdir(exist_ok=True)
    base=f"http://{host}:{port}"
    guard=socket.socket()
    try:
        guard.bind(("127.0.0.1",18765))
        guard.listen(1)
    except OSError:
        raise RuntimeError("VTX station watchdog already running (or port 18765 occupied)")
    env=dict(os.environ,PYTHONPATH=str(ROOT/"src"),MUJOCO_GL="disable")
    server=None
    pilot=None
    server_log=(LOGS/"station-server.log").open("a",encoding="utf-8")
    pilot_log=(LOGS/"station-pilot.log").open("a",encoding="utf-8")
    last_server_launch=-1e6
    last_pilot_launch=-1e6
    try:
        stamp("Station watching "+base)
        while True:
            now=time.monotonic()
            online=server_alive(base)
            if not online and now-last_server_launch>=8 and (server is None or server.poll() is not None):
                server=subprocess.Popen([sys.executable,"-u",str(ROOT/"scripts"/"launch_pc.py")],
                    cwd=ROOT,env=env,stdout=server_log,stderr=subprocess.STDOUT)
                last_server_launch=now
                stamp("Server launched PID "+str(server.pid))
            if pilot is None or pilot.poll() is not None:
                if now-last_pilot_launch>=5:
                    pilot=subprocess.Popen([sys.executable,"-u",str(ROOT/"tools"/"persistent_pilot.py"),
                        "--base",base],cwd=ROOT,env=env,
                        stdout=pilot_log,stderr=subprocess.STDOUT)
                    last_pilot_launch=now
                    stamp("Pilot launched PID "+str(pilot.pid))
            time.sleep(interval)
    finally:
        stamp("Station stopping owned processes")
        if pilot is not None and pilot.poll() is None:
            pilot.terminate()
        if server is not None and server.poll() is None:
            server.terminate()
        server_log.close()
        pilot_log.close()
        guard.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--host",default=HOST)
    parser.add_argument("--port",type=int,default=PORT)
    args=parser.parse_args()
    try:
        supervise(args.host,args.port)
    except KeyboardInterrupt:
        pass
