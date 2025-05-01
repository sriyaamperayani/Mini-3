import grpc
import psutil
import time
import threading
import random
import sys
from concurrent import futures
import election_pb2
import election_pb2_grpc


class Node(election_pb2_grpc.ElectionServiceServicer):
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers  # List of (address, port)

        self.peer_map = {
            ("localhost", 50051): "node1",
            ("localhost", 50052): "node2",
            ("localhost", 50053): "node3",
            ("localhost", 50054): "node4",
            ("localhost", 50055): "node5",
        }

        self.node_position_map = {
            "node1": 0,
            "node2": 1,
            "node3": 2,
            "node4": 3,
            "node5": 4,
        }
        self.node_position = self.node_position_map.get(self.node_id, -1)
        self.max_steal_distance = 2

        self.is_leader = False
        self.leader_id = None
        self.start_time = time.time()
        self.score = self.calculate_score()
        self.votes_received = 0
        self.alive = True
        self.successful_steals = 0
        self.last_steal_time = 0
        self.steal_interval = 5
        self.floor_cpu_threshold = 70

        from collections import deque
        self.task_queue = deque()
        self.task_history = set()
        self.completed_tasks = 0

    def calculate_score(self):
        cpu_available = 100.0 - psutil.cpu_percent(interval=0.1)
        memory_available = psutil.virtual_memory().available / (1024 * 1024)
        uptime = time.time() - self.start_time
        jitter = random.uniform(-1, 1)
        print(f"[{self.node_id}] Raw Metrics - CPU: {cpu_available:.2f}, Mem: {memory_available:.2f}, Uptime: {uptime:.2f}")
        score = (0.5 * cpu_available) + (0.3 * (memory_available / 1000)) + (0.2 * (uptime / 60)) + jitter
        return score

    def attempt_work_steal(self):
        now = time.time()
        if now - self.last_steal_time < self.steal_interval:
            return
        self.last_steal_time = now

        cpu_available = 100.0 - psutil.cpu_percent(interval=0.1)
        if cpu_available < self.floor_cpu_threshold:
            print(f"[{self.node_id}] Skipping steal: CPU load too high.")
            return

        for address, port in self.peers:
            target_id = self.peer_map.get((address, port), "unknown")
            target_pos = self.node_position_map.get(target_id, 999)
            if abs(target_pos - self.node_position) > self.max_steal_distance:
                continue

            try:
                channel = grpc.insecure_channel(f'{address}:{port}')
                stub = election_pb2_grpc.ElectionServiceStub(channel)
                response = stub.WorkRequest(election_pb2.WorkRequestMessage(requester_id=self.node_id))
                if response.assigned_to != "unknown" and response.task_id != "none":
                    print(f"[{self.node_id}] Steal successful. Assigned to: {response.assigned_to}, Task: {response.task_id}")
                    self.successful_steals += 1
                break
            except Exception as e:
                continue

    def Heartbeat(self, request, context):
        if not self.leader_id or request.node_id != self.leader_id:
            print(f"[{self.node_id}] Accepting new leader: {request.node_id}")
            self.leader_id = request.node_id
        return election_pb2.HeartbeatResponse(success=True, message="Heartbeat received")

    def RequestVote(self, request, context):
        return election_pb2.VoteResponse(vote_granted=request.candidate_score >= self.score)

    def WorkRequest(self, request, context):
        if not self.is_leader:
            return election_pb2.WorkAssignment(assigned_to=self.leader_id or "unknown", task_id="none")

        task_id = f"Task-{self.node_id}-{int(time.time() * 1000)}"
        target = random.choice(self.peers)
        node_id = self.peer_map.get(target, "unknown")

        try:
            channel = grpc.insecure_channel(f'{target[0]}:{target[1]}')
            stub = election_pb2_grpc.ElectionServiceStub(channel)
            response = stub.AssignTask(election_pb2.TaskMessage(task_id=task_id))
            print(f"[{self.node_id}] Assigned {task_id} to {node_id}, Status: {response.status}")
            return election_pb2.WorkAssignment(assigned_to=node_id, task_id=task_id)
        except Exception as e:
            return election_pb2.WorkAssignment(assigned_to="error", task_id="none")

    def AssignTask(self, request, context):
        task_id = request.task_id
        if task_id in self.task_history:
            print(f"[{self.node_id}] Duplicate task {task_id} ignored (idempotent)")
            return election_pb2.Ack(status="already_processed", message="Task already handled")

        self.task_queue.append(task_id)
        self.task_history.add(task_id)
        print(f"[{self.node_id}] Task {task_id} enqueued. Queue length: {len(self.task_queue)}")
        threading.Thread(target=self.process_task, args=(task_id,)).start()
        return election_pb2.Ack(status="accepted", message="Task accepted")

    def process_task(self, task_id):
        print(f"[{self.node_id}] Processing {task_id}...")
        time.sleep(random.randint(1, 3))
        print(f"[{self.node_id}] Completed {task_id}")
        self.completed_tasks += 1

    def start_server(self, port):
        self.port = port
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        election_pb2_grpc.add_ElectionServiceServicer_to_server(self, server)
        server.add_insecure_port(f'[::]:{port}')
        server.start()
        print(f"Node {self.node_id} started at port {port}")
        threading.Thread(target=self.heartbeat_loop).start()
        server.wait_for_termination()

    def heartbeat_loop(self):
        while self.alive:
            time.sleep(3)
            for address, port in self.peers:
                try:
                    channel = grpc.insecure_channel(f'{address}:{port}')
                    stub = election_pb2_grpc.ElectionServiceStub(channel)
                    stub.Heartbeat(election_pb2.HeartbeatRequest(node_id=self.node_id, score=self.score))
                except:
                    continue

            if not self.leader_id and self.alive:
                print(f"[{self.node_id}] No leader detected. Trying election...")
                self.initiate_election()

            self.attempt_work_steal()

            if int(time.time()) % 30 == 0:
                print(f"[{self.node_id}] Steal count: {self.successful_steals}")

            if int(time.time()) % 15 == 0:
                print(f"[{self.node_id}] Current leader: {self.leader_id}")

    def initiate_election(self):
        print(f"Node {self.node_id} initiating election.")
        votes = 1
        for address, port in self.peers:
            try:
                channel = grpc.insecure_channel(f'{address}:{port}')
                stub = election_pb2_grpc.ElectionServiceStub(channel)
                response = stub.RequestVote(election_pb2.VoteRequest(candidate_id=self.node_id, candidate_score=self.score))
                if response.vote_granted:
                    votes += 1
            except:
                continue

        if votes > (len(self.peers) + 1) // 2:
            print(f"Node {self.node_id} becomes leader with {votes} votes and score {self.score:.2f}!")
            self.is_leader = True
            self.leader_id = self.node_id
            for address, port in self.peers:
                try:
                    channel = grpc.insecure_channel(f'{address}:{port}')
                    stub = election_pb2_grpc.ElectionServiceStub(channel)
                    stub.Heartbeat(election_pb2.HeartbeatRequest(node_id=self.node_id, score=self.score))
                except:
                    continue
        else:
            print(f"Node {self.node_id} failed to become leader. Score was {self.score:.2f}.")
            self.is_leader = False


if __name__ == "__main__":
    node_id = sys.argv[1]
    port = int(sys.argv[2])
    peers = []
    for peer_info in sys.argv[3:]:
        address, port_str = peer_info.split(":")
        peers.append((address, int(port_str)))

    node = Node(node_id, peers)
    node.start_server(port)
