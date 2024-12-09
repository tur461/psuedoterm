#!/bin/bash
CMD="$1"
SID="$2"
curl -X POST http://localhost:5000/exec_cmd -H "Content-Type: application/json" -d "{\"s_id\": \"$SID\", \"cmd\": \"$CMD\"}"
