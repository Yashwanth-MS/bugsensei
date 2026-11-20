import http.server
import socketserver
import os
import sys

PORT = 8501
DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")

class SPAServer(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        '.js': 'application/javascript',
        '.mjs': 'application/javascript',
        '.css': 'text/css',
        '.html': 'text/html',
        '.png': 'image/png',
        '.svg': 'image/svg+xml',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_GET(self):
        # SPA fallback: if file does not exist, serve index.html
        path = self.translate_path(self.path)
        if not os.path.exists(path) and not '.' in os.path.basename(path):
            self.path = '/index.html'
        return super().do_GET()

    def end_headers(self):
        # Enable CORS and caching headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

if __name__ == '__main__':
    # Allow quick port reuse
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", PORT), SPAServer) as httpd:
        print(f"Serving BugSensei Dashboard on http://0.0.0.0:{PORT} from {DIRECTORY}")
        httpd.serve_forever()
