import http.server, sys, os, functools
PUB = '/home/user/-vtx-flight-sim/public'; PAGE = sys.argv[2]
class H(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        if path.split('?')[0] == '/render.html': return PAGE
        return super().translate_path(path)
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1])), functools.partial(H, directory=PUB)).serve_forever()
