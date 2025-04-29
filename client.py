import grpc
import time
import random
import threading
import sys
import election_pb2
import election_pb2_grpc

# SETTINGS
LEADER_ADDRESS = "localhost"
LEADER_PORT = 50051  # Assuming node1 is leader initially
REQUEST_RATE = 1  # requests per second (can adjust to 5, 10, etc.)

def send_task(requester_id):
    try:
        channel = grpc.insecure_channel(f"{LEADER_ADDRESS}:{LEADER_PORT}")
        stub = election_pb2_grpc.ElectionServiceStub(channel)

        while True:
            response = stub.WorkRequest(
                election_pb2.WorkRequestMessage(requester_id=requester_id)
            )
            print(f"[CLIENT] Sent task request, assigned to: {response.assigned_to}, Task: {response.task_id}")
            time.sleep(1 / REQUEST_RATE)  # regulate speed
    except KeyboardInterrupt:
        print("Client stopped manually.")
    except Exception as e:
        print(f"[CLIENT] Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        REQUEST_RATE = int(sys.argv[1])  # Allow user to set custom rate

    requester_id = f"client-{random.randint(1000,9999)}"
    print(f"Client {requester_id} started, sending {REQUEST_RATE} tasks/sec to {LEADER_ADDRESS}:{LEADER_PORT}")
    send_task(requester_id)
