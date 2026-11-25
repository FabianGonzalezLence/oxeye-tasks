#!/bin/sh
cd "$(dirname "$0")"
echo "OxEye · Abre http://localhost:8765"
python3 servidor.py --host 0.0.0.0 --port 8765
