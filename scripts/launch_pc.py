"""Launch a local, single-operator simulator and open it after startup."""
from pathlib import Path
import sys
import threading
import time
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
URL='http://127.0.0.1:8765/'


def open_when_ready(server):
    for _ in range(60):
        if server.started:
            webbrowser.open(URL)
            return
        time.sleep(.5)
    print('Browser was not opened automatically. Check the server output.',flush=True)


if __name__=='__main__':
    import uvicorn
    server=uvicorn.Server(uvicorn.Config('vtx.live_server:app',host='127.0.0.1',port=8765,log_level='warning'))
    threading.Thread(target=open_when_ready,args=(server,),daemon=True).start()
    server.run()
