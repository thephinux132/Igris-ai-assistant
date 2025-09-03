"""
LAN Topology Scanner Plugin

Scans local subnet using ping and optional nmap (if installed).
Collects IPs, MACs, hostnames and prints device summary.
"""

def run():
    import subprocess, platform, re, socket

    def get_ip_range():
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        subnet = ".".join(local_ip.split(".")[:3]) + ".0/24"
        return subnet

    def is_tool(name):
        from shutil import which
        return which(name) is not None

    print("=== LAN Topology Scanner ===")
    subnet = get_ip_range()
    print(f"[INFO] Scanning subnet: {subnet}")

    if is_tool("nmap"):
        cmd = f"nmap -sn {subnet}"
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        output = result.stdout.splitlines()
        hosts = []
        current = {}
        for line in output:
            if "Nmap scan report for" in line:
                current = {"ip": line.split()[-1]}
            elif "MAC Address" in line:
                mac_info = line.split("MAC Address: ")[1]
                current["mac"] = mac_info.split(" ")[0]
                current["vendor"] = " ".join(mac_info.split(" ")[1:]).strip("()")
                hosts.append(current)
        if not hosts:
            return "[WARN] No live hosts found."
        report = "\n".join([f"{h.get('ip')} - {h.get('mac', 'N/A')} ({h.get('vendor', 'Unknown')})" for h in hosts])
        return f"Live Hosts:\n{report}"
    else:
        return "[ERROR] 'nmap' is required. Install it and try again."