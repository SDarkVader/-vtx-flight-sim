import sys
from pathlib import Path
import socket
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

def forward_stream(source, destination):
    try:
        while True:
            data = source.recv(4096)
            if not data:
                break
            destination.sendall(data)
    except Exception:
        pass
    finally:
        try:
            source.close()
        except Exception:
            pass
        try:
            destination.close()
        except Exception:
            pass

def proxy_port(listen_port, target_port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', listen_port))
    server.listen(100)
    print(f"[Proxy] Forwarding 0.0.0.0:{listen_port} -> 127.0.0.1:{target_port}", flush=True)
    while True:
        client_sock, _ = server.accept()
        try:
            target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_sock.connect(('127.0.0.1', target_port))
            t1 = threading.Thread(target=forward_stream, args=(client_sock, target_sock), daemon=True)
            t2 = threading.Thread(target=forward_stream, args=(target_sock, client_sock), daemon=True)
            t1.start()
            t2.start()
        except Exception as e:
            print(f"[Proxy Error] {e}", flush=True)
            client_sock.close()

if __name__ == '__main__':
    # Start proxy on 8768 in background thread
    threading.Thread(target=proxy_port, args=(8768, 8765), daemon=True).start()
    
    import uvicorn
    print("[Server] Starting uvicorn on 0.0.0.0:8765 (accessible from LAN & Localhost)...", flush=True)
    uvicorn.run('vtx.live_server:app', host='0.0.0.0', port=8765, log_level='info')
