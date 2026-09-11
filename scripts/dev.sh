#!/usr/bin/env bash
# Start registry + five delegates + UI locally. FOREMAN_FAKE_LLM=1 runs with no API key.
cd "$(dirname "$0")/.." && source .venv/bin/activate
mkdir -p runs; : > runs/dev.log
for d in researcher analyst writer quickfix oracle; do nohup python -m delegates.serve $d >> runs/dev.log 2>&1 & done
nohup python -m registry.main >> runs/dev.log 2>&1 &
nohup python -m ui.app >> runs/dev.log 2>&1 &
sleep 5; echo "UI http://localhost:8080  registry http://localhost:8100/agents  log runs/dev.log"
