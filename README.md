# 🗳️ CMPE 275 Mini Project 3: Consensus-Based Work Allocation with Dynamic Leadership

## 📌 Objective

This project implements a decentralized, leader-election-based distributed system that assigns and balances workload across multiple nodes using gRPC. It explores core distributed systems concepts including:

- Consensus-based dynamic leadership
- Intelligent work distribution and task stealing
- CPU-aware task assignment
- Fault tolerance and node failure recovery
- Real-time metrics scoring

---

## 🧠 Features Implemented

### ✅ 1. Dynamic Leader Election
- Nodes vote for a leader based on a calculated **score** derived from:
  - CPU availability
  - Memory availability
  - Uptime (with added jitter)
- Each node broadcasts a `RequestVote` RPC to others.
- Leader is elected with majority votes.

### ✅ 2. Score Calculation (Real Metrics)
- **CPU**: `100 - psutil.cpu_percent()`
- **Memory**: `psutil.virtual_memory().available`
- **Uptime**: `current_time - node_start_time`
- Score = `w1*CPU + w2*MEMORY + w3*UPTIME + jitter`

### ✅ 3. Task Assignment
- Only the **elected leader** assigns tasks.
- Uses `WorkRequest` and `AssignTask` RPCs.
- Assigns task to random eligible peer within communication range.

### ✅ 4. Task Processing with Idempotence
- Each node runs a thread to **simulate task execution**.
- Duplicate tasks are ignored using `task_history`.

### ✅ 5. Intelligent Work Stealing
- Nodes attempt to **steal work** if underutilized.
- Steal cooldown (`5s`) and CPU floor (`70%`) enforced.
- Only steal from nodes within `max_steal_distance = 2`.

### ✅ 6. Communication Limits
- Simulated “distance” between nodes via `node_position_map`.
- Ensures that nodes don't blindly attempt to steal work from far nodes.

### ✅ 7. Failure Handling
- Nodes **simulate failure** randomly.
- If leader fails, remaining nodes auto-trigger election.

### ✅ 8. gRPC Interface (Proto)
Supports:
- `RequestVote`
- `Heartbeat`
- `WorkRequest`
- `AssignTask`

---

## 📂 File Structure

```bash
mini3/
├── client.py                 # Optional: used for debugging or manual testing
├── server.py                 # Main logic for each node
├── election.proto            # Proto file defining gRPC messages & services
├── election_pb2.py           # Generated from proto
├── election_pb2_grpc.py      # Generated from proto
├── start_servers.sh          # Shell script to spawn 5 servers
├── stop_servers.sh           # Stops all server processes
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- gRPC tools
- psutil

### Install gRPC and psutil:
```bash
pip install grpcio grpcio-tools psutil
```

### Generate gRPC Code:
```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. election.proto
```

---

## 🧪 Running the System

### Step 1: Start all nodes
```bash
chmod +x start_servers.sh
./start_servers.sh
```

### Step 2: Stop all nodes
```bash
chmod +x stop_servers.sh
./stop_servers.sh
```
