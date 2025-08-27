hostname R1
interface GigabitEthernet0/0
 ip address 192.168.1.1 255.255.255.0
 mtu 1500
interface GigabitEthernet0/1
 ip address 10.0.0.1 255.255.255.0
 mtu 1500
vlan 10
