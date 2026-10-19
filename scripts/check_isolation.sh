#!/bin/sh
# Blue-team code must not read labels or import the red-team package; the bank-node and radar code must not import eval/ (labels live there).
# Fails (exit 1) on any hit.
bad=0
if grep -rnE "^\s*(import|from)\s+redteam\b|labels\.parquet" node radar copilot audit escalation export api common ingest --include=*.py; then bad=1; fi
if grep -rnE "^\s*(import|from)\s+eval\b" node radar copilot audit escalation export common ingest --include=*.py; then bad=1; fi
if [ "$bad" = "1" ]; then echo "ISOLATION VIOLATION"; exit 1; fi
echo "isolation ok"
