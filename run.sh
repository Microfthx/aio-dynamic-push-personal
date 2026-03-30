#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cat <<EOF
This repository is configured for local Python execution, not Docker.

Recommended commands:

1. Start with the managed script:
   cd "$PROJECT_DIR"
   ./start.sh

2. Or start manually with your proxy settings:
   cd "$PROJECT_DIR"
   nohup env \\
     http_proxy=http://127.0.0.1:17890 \\
     https_proxy=http://127.0.0.1:17890 \\
     all_proxy=socks5://127.0.0.1:17891 \\
     python3 -u main.py > aio-dynamic-push.log 2>&1 &

3. Restart:
   cd "$PROJECT_DIR"
   ./restart.sh
EOF
