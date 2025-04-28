#!/bin/bash

# Check if PID file exists
if [ ! -f server_pids.txt ]; then
  echo "No server_pids.txt found. Are the servers running?"
  exit 1
fi

# Kill all PIDs listed
while read pid; do
  kill $pid
done < server_pids.txt

# Clean up
rm server_pids.txt
echo "All servers stopped and PID file deleted."
