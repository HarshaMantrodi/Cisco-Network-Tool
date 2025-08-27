import os
import json
import ipaddress
from collections import defaultdict, deque
import threading
import time
from queue import Queue, Empty

# (Parsing and static analysis functions remain the same)
def parse_config_file(filepath):
    device_id = os.path.basename(os.path.dirname(filepath))
    device_details = { 'hostname': None, 'interfaces': {}, 'default_route': None, 'ospf_enabled': False }
    current_interface = None
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith("hostname"): device_details['hostname'] = line.split()[1]
            elif line.startswith("interface"): current_interface = line.split()[1]; device_details['interfaces'][current_interface] = {}
            elif line.startswith("router ospf"): device_details['ospf_enabled'] = True
            elif line.startswith("description") and current_interface: device_details['interfaces'][current_interface]['description'] = ' '.join(line.split()[1:])
            elif line.startswith("ip address") and current_interface:
                parts = line.split(); device_details['interfaces'][current_interface]['ip_address'] = parts[2]; device_details['interfaces'][current_interface]['subnet_mask'] = parts[3]
    return device_id, device_details
def build_topology(devices_data):
    links = []
    device_ids = list(devices_data.keys())
    for i in range(len(device_ids)):
        for j in range(i + 1, len(device_ids)):
            dev1_id, dev2_id = device_ids[i], device_ids[j]
            dev1_interfaces = devices_data[dev1_id].get('interfaces', {})
            dev2_interfaces = devices_data[dev2_id].get('interfaces', {})
            for int1_name, int1_details in dev1_interfaces.items():
                for int2_name, int2_details in dev2_interfaces.items():
                    if 'ip_address' in int1_details and 'ip_address' in int2_details:
                        try:
                            net1 = ipaddress.IPv4Interface(f"{int1_details['ip_address']}/{int1_details['subnet_mask']}").network
                            net2 = ipaddress.IPv4Interface(f"{int2_details['ip_address']}/{int2_details['subnet_mask']}").network
                            if net1 == net2:
                                links.append({"from_device": dev1_id, "from_interface": int1_name, "to_device": dev2_id, "to_interface": int2_name})
                        except (ValueError, ipaddress.AddressValueError): pass
    return links
def load_configurations():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    conf_dir = os.path.join(project_root, 'Conf')
    loaded_devices = {}
    if not os.path.isdir(conf_dir):
        print(f"Error: Directory not found: {conf_dir}")
        return {}
    for device_folder in os.listdir(conf_dir):
        config_file_path = os.path.join(conf_dir, device_folder, 'config.dump')
        if os.path.isfile(config_file_path):
            device_id, details = parse_config_file(config_file_path)
            if device_id and details: loaded_devices[device_id] = details
    return loaded_devices

# ==========================================================
# NEW NETWORK SWITCH CLASS FOR IPC
# ==========================================================
class NetworkSwitch:
    """A virtual switch to handle message passing between router threads."""
    def __init__(self):
        self.queues = defaultdict(Queue)

    def send_packet(self, destination_id, packet):
        self.queues[destination_id].put(packet)

    def receive_packet(self, device_id):
        try:
            return self.queues[device_id].get(block=False)
        except Empty:
            return None

# ==========================================================
# ROUTER CLASS UPDATED FOR IPC
# ==========================================================
class Router(threading.Thread):
    def __init__(self, device_id, config_data, network_switch, links):
        super().__init__()
        self.device_id = device_id
        self.hostname = config_data.get('hostname', device_id)
        self.network_switch = network_switch
        self.log = []
        self.is_running = True
        
        # Find neighbors from the topology data
        self.neighbors = []
        for link in links:
            if link['from_device'] == self.device_id:
                self.neighbors.append(link['to_device'])
            elif link['to_device'] == self.device_id:
                self.neighbors.append(link['from_device'])

    def run(self):
        self.log_message(f"Thread started. Neighbors: {self.neighbors}")
        last_hello_time = 0

        while self.is_running:
            # --- RECEIVE LOGIC ---
            packet = self.network_switch.receive_packet(self.device_id)
            if packet:
                self.log_message(f"Received '{packet['type']}' from {packet['source']}")

            # --- SEND LOGIC ---
            # Send a "Hello" packet every 2 seconds
            if time.time() - last_hello_time > 2:
                for neighbor in self.neighbors:
                    hello_packet = {"source": self.hostname, "type": "OSPF_HELLO"}
                    self.network_switch.send_packet(neighbor, hello_packet)
                    self.log_message(f"Sent 'OSPF_HELLO' to {neighbor}")
                last_hello_time = time.time()
            
            time.sleep(0.1) # Small sleep to prevent busy-looping
        
        self.log_message(f"Thread finished.")

    def log_message(self, message):
        log_entry = f"[{time.strftime('%H:%M:%S')}] [{self.hostname}] {message}"
        self.log.append(log_entry)
        print(log_entry)

# ==========================================================
# MAIN FUNCTION UPDATED FOR IPC
# ==========================================================
def main():
    """Main function to run the interactive tool."""
    network_devices_data = load_configurations()
    if not network_devices_data:
        return
    
    topology = build_topology(network_devices_data)
    router_threads = []
    # Create a single switch for all threads to share
    network_switch = NetworkSwitch() 

    while True:
        print("\n" + "="*20 + " Main Menu " + "="*20)
        print("1. Display Network Topology")
        print("2. Start IPC Simulation")
        print("3. View Last Simulation Logs")
        print("4. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            print("\n--- Discovered Network Links ---")
            for link in topology:
                print(f"{link['from_device']}({link['from_interface']}) <--> {link['to_device']}({link['to_interface']})")

        elif choice == '2':
            if any(t.is_alive() for t in router_threads):
                print("Simulation is already running.")
                continue
            
            print("\n--- Starting IPC Simulation (runs for 10 seconds) ---")
            router_threads = []
            for device_id, config in network_devices_data.items():
                if "R" in device_id:
                    router = Router(device_id, config, network_switch, topology)
                    router_threads.append(router)
                    router.start()
            
            # Let the simulation run for a set duration
            time.sleep(10)
            # Signal all threads to stop
            for router in router_threads:
                router.is_running = False
            # Wait for all threads to complete
            for t in router_threads:
                t.join()
            print("--- Simulation Complete ---")

        elif choice == '3':
            if not router_threads:
                print("\nNo simulation has been run yet. Please run option 2 first.")
                continue
            
            print("\n--- Last Simulation Logs ---")
            for router in sorted(router_threads, key=lambda r: r.hostname):
                print(f"\n--- Log for Device: {router.hostname} ---")
                for msg in router.log:
                    print(msg)

        elif choice == '4':
            print("Exiting tool.")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()