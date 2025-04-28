import grpc
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
        self.is_leader = False
        self.leader_id = None
        self.score = self.calculate_score()
        self.votes_received = 0
        self.alive = True

    def calculate_score(self):
        # Dummy formula (customize if you want)
        return random.uniform(0, 100)

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
            assigned = min(self.peers + [("localhost", self.port)], key=lambda x: random.random())[0]
            return election_pb2.WorkAssignment(assigned_to=assigned)
        else:
            return election_pb2.WorkAssignment(assigned_to=self.leader_id)

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
            print(f"Node {self.node_id} becomes leader with {votes} votes!")
            self.is_leader = True
            self.leader_id = self.node_id
        else:
            print(f"Node {self.node_id} failed to become leader.")
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
