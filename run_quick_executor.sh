#!/bin/bash
# MT.OS Quick Executor — Run immediately
cd "$(dirname "$0")" || exit 1
python3 -m mt_sync_engine.quick_executor
