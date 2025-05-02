#!/bin/bash

# Clear previous PID file if exists
rm -f server_pids.txt

python3 server.py node1 50051 localhost:50052 localhost:50053 localhost:50054 localhost:50055 &
echo $! >> server_pids.txt

python3 server.py node2 50052 localhost:50051 localhost:50053 localhost:50054 localhost:50055 &
echo $! >> server_pids.txt

python3 server.py node3 50053 localhost:50051 localhost:50052 localhost:50054 localhost:50055 &
echo $! >> server_pids.txt

python3 server.py node4 50054 localhost:50051 localhost:50052 localhost:50053 localhost:50055 &
echo $! >> server_pids.txt

python3 server.py node5 50055 localhost:50051 localhost:50052 localhost:50053 localhost:50054 &
echo $! >> server_pids.txt

echo "Started 5 servers! PIDs stored in server_pids.txt"
