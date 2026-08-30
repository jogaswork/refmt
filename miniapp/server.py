import os
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

PORT = int(os.environ.get("PORT", 8080))

server = ThreadingHTTPServer(
    ("0.0.0.0", PORT),
    SimpleHTTPRequestHandler
)

print(f"Mini App running on port {PORT}")

server.serve_forever()
