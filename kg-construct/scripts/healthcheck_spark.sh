#!/usr/bin/env bash
set -euo pipefail

host="${1:-127.0.0.1}"
port="${2:?port is required}"

python3 - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

sock = socket.socket()
sock.settimeout(3)
try:
    sock.connect((host, port))
except OSError:
    sys.exit(1)
finally:
    sock.close()
PY
