""" 
Diagnose Network Stack
Checks adapter IP, subnet, ARP visibility, and Scapy usability.
"""
import socket
import os
import subprocess
import platform

def run():
    output = []

    # 1. IP Address Check
    output.append("🧠 Network Adapter Info:")
    try:
        ip = socket.gethostbyname(socket.gethostname())
        output.append(f"  • IPv4 Address: {ip}")
        subnet = ".".join(ip.split(".")[:3]) + ".0/24"
        output.append(f"  • Assumed Subnet: {subnet}")
    except Exception as e:
        output.append(f"  ❌ Failed to retrieve IP: {e}")

    # 2. ARP Table
    output.append("\n📡 ARP Table Scan:")
    try:
        if platform.system() == "Windows":
            result = subprocess.check_output(["arp", "-a"], text=True)
        else:
            result = subprocess.check_output(["ip", "neigh"], text=True)
        lines = [line for line in result.split("\n") if line.strip()]
        if lines:
            output.extend(["  • " + line for line in lines[:10]])
        else:
            output.append("  ❌ ARP table is empty.")
    except Exception as e:
        output.append(f"  ❌ Failed to retrieve ARP table: {e}")

    # 3. Scapy Layer Check
    output.append("\n⚙️ Scapy ARP Broadcast Test:")
    try:
        from scapy.all import ARP, Ether, srp
        pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=subnet)
        ans, _ = srp(pkt, timeout=2, verbose=False)
        if ans:
            output.append(f"  ✅ {len(ans)} ARP response(s) received.")
            for _, r in ans[:5]:
                output.append(f"    → {r.psrc} - {r.hwsrc}")
        else:
            output.append("  ❌ No ARP responses received.")
    except ImportError:
        output.append("  ❌ Scapy is not installed.")
    except Exception as e:
        output.append(f"  ❌ Scapy error: {e}")

    return "\n".join(output)

if __name__ == "__main__":
    print(run())
