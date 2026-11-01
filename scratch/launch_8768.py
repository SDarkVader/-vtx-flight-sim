import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('vtx.live_server:app', host='127.0.0.1', port=8768, log_level='info')
