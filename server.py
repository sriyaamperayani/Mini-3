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
        
        # Map (address, port) to node_id
        self.peer_map = {
            ("localhost", 50051): "node1",
            ("localhost", 50052): "node2",
            ("localhost", 50053): "node3",
            ("localhost", 50054): "node4",
            ("localhost", 50055): "node5",
        }
        
        self.is_leader = False
        self.leader_id = None
        self.start_time = time.time()
        self.score = self.calculate_score()
        self.votes_received = 0
        self.alive = True
        self.successful_steals = 0
        self.last_steal_time = 0  # Track last steal attempt
        self.steal_interval = 5   # Minimum 5 seconds between steals
        self.floor_cpu_threshold = 70  # Only steal if CPU availability > 70%


    def calculate_score(self):
        # Real metrics calculation
        cpu_available = 100.0 - psutil.cpu_percent(interval=0.1)  # CPU available %
        memory_available = psutil.virtual_memory().available / (1024 * 1024)  # in MB
        uptime = time.time() - self.start_time  # seconds running
        
        # Weights
        w1 = 0.5  # CPU availability weight
        w2 = 0.3  # Memory availability weight
        w3 = 0.2  # Uptime weight
        
        score = (w1 * cpu_available) + (w2 * (memory_available / 1000)) + (w3 * (uptime / 60))
        
        return score

    def attempt_work_steal(self):
        now = time.time()
    
        # Respect steal cooldown
        if now - self.last_steal_time < self.steal_interval:
            return
    
        self.last_steal_time = now
        cpu_available = 100.0 - psutil.cpu_percent(interval=0.1)
        
        if cpu_available < self.floor_cpu_threshold:
            print(f"[{self.node_id}] Skipping steal: CPU load too high.")
            return
    
        print(f"[{self.node_id}] Attempting to steal work...")
        for address, port in self.peers:
            try:
                channel = grpc.insecure_channel(f'{address}:{port}')
                stub = election_pb2_grpc.ElectionServiceStub(channel)
                
                # You can implement a `StealWork()` RPC or use WorkRequest with a 'steal' flag
                response = stub.WorkRequest(election_pb2.WorkRequestMessage(requester_id=self.node_id))

                if response.assigned_to != "unknown":
                    print(f"[{self.node_id}] Steal successful. Assigned to: {response.assigned_to}, Task: {response.task_id}")
                    self.successful_steals += 1
                else:
                    print(f"[{self.node_id}] Steal failed: no task assigned.")
                break  # Stop after first steal attempt

            except Exception as e:
                print(f"[{self.node_id}] Steal attempt failed to {address}:{port}")

    
    def Heartbeat(self, request, context):
        # Accept heartbeat from another node
        return election_pb2.HeartbeatResponse(success=True)

    def RequestVote(self, request, context):
        if request.candidate_score >= self.score:
            return election_pb2.VoteResponse(vote_granted=True)
        else:
            return election_pb2.VoteResponse(vote_granted=False)

    def WorkRequest(self, request, context):
        # Leader assigns the work
        if self.is_leader:
            # Pick a random peer to assign work to (you can improve this later)
            target = random.choice(self.peers)
            node_id = self.peer_map.get(target, "unknown")
            task_id = f"Task-{int(time.time()) % 10000}"  # Simple unique ID
            
            print(f"[{self.node_id}] Assigning {task_id} to {node_id}")
            #assigned = min(self.peers + [("localhost", self.port)], key=lambda x: random.random())[0]
            return election_pb2.WorkAssignment(assigned_to=node_id, task_id=task_id)
        else:
            return election_pb2.WorkAssignment(assigned_to=self.leader_id, task_id="none")

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
                except Exception as e:
                    print(f"[WARN] Heartbeat to {address}:{port} failed.")

            # Randomly simulate failure
            if random.random() < 0.05:
                print(f"Node {self.node_id} simulating failure.")
                self.alive = False

            # Leader election if no leader
            if not self.leader_id:
                self.initiate_election()
                
            self.attempt_work_steal()
            
            if int(time.time()) % 30 == 0:
                print(f"[{self.node_id}] Steal count: {self.successful_steals}")


    def initiate_election(self):
        print(f"Node {self.node_id} initiating election.")
        votes = 1  # Vote for self
        for address, port in self.peers:
            try:
                channel = grpc.insecure_channel(f'{address}:{port}')
                stub = election_pb2_grpc.ElectionServiceStub(channel)
                response = stub.RequestVote(election_pb2.VoteRequest(candidate_id=self.node_id, candidate_score=self.score))
                if response.vote_granted:
                    votes += 1
            except Exception as e:
                continue

        if votes > (len(self.peers) + 1) // 2:
            print(f"Node {self.node_id} becomes leader with {votes} votes and score {self.score:.2f}!")
            self.is_leader = True
            self.leader_id = self.node_id
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
