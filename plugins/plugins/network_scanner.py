"""
Network Scanner Plugin (Refactored)
Scans a given subnet using ARP to retrieve IP, MAC, and hostnames.
Requires: scapy
"""
from scapy.all import ARP, Ether, srp
import socket

def scan_subnet(subnet="192.168.1.0/24"):
    packet = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet)
    result = srp(packet, timeout=2, verbose=False)[0]
    devices = []
    for sent, received in result:
        try:
            hostname = socket.gethostbyaddr(received.psrc)[0]
        except socket.herror:
            hostname = "Unknown"
        devices.append({
            "ip": received.psrc,
            "mac": received.hwsrc,
            "hostname": hostname
        })
    return devices

def run():
    subnet = input("Enter subnet to scan (e.g. 192.168.1.0/24): ") or "192.168.1.0/24"
    results = scan_subnet(subnet)
    output = "Discovered Devices:\n"
    for device in results:
        output += f"{device['ip']} | {device['mac']} | {device['hostname']}\n"
    return output.strip()