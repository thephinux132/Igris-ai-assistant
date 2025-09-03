"""
Network Scanner Plugin (Hardened)
- Prefers Scapy ARP scan (fast), but gracefully falls back to ping+ARP table.
- Lets caller choose interface/subnet; auto-detects sane default otherwise.
- Works on Windows (Npcap) and non-admin by using fallbacks when needed.
"""
from __future__ import annotations
import ipaddress, os, platform, socket, subprocess, sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple


# ──────────────────────────────────────────────────────────────────────────────
# Try Scapy, but don't crash if unavailable or lacks permissions
_SCAPY_OK = False

class Host:
    __slots__ = ("ip", "mac", "hostname")
    def __init__(self, ip: str, mac: str, hostname: str = "Unknown"):
        self.ip = ip
        self.mac = mac
        self.hostname = hostname

def _default_ipv4() -> Optional[str]:
    try:
        # More reliable than gethostbyname(gethostname()) on Windows
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return None

def _derive_cidr(ip: str) -> str:
    # Assume /24 unless told otherwise; safe default for LAN scans
    parts = ip.split(".")
    return ".".join(parts[:3]) + ".0/24"

def _reverse_dns(ip: str) -> str:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return "Unknown"

def _scan_scapy(cidr: str, timeout: int = 3) -> List[Host]:
    pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=cidr)
    try:
        ans = srp(pkt, timeout=timeout, verbose=False)[0]
    except Exception:
        return []
    hosts: List[Host] = []
    for _, r in ans:
        hosts.append(Host(ip=r.psrc, mac=r.hwsrc, hostname=_reverse_dns(r.psrc)))
    return hosts

def _ping(host: str, timeout_ms: int = 300) -> None:
    if platform.system().lower().startswith("win"):
        subprocess.run(["ping", "-n", "1", "-w", str(timeout_ms), host],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), host],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def _read_arp_table() -> List[Tuple[str, str]]:
    """Return list of (ip, mac) from OS ARP table."""
    out = ""
    try:
        if platform.system().lower().startswith("win"):
            out = subprocess.check_output(["arp", "-a"], text=True, encoding="utf-8", errors="replace")
        else:
            out = subprocess.check_output(["arp", "-an"], text=True, encoding="utf-8", errors="replace")
    except Exception:
        return []
    pairs: List[Tuple[str, str]] = []
    for line in out.splitlines():
        line = line.strip()
        # Windows: 192.168.1.10         00-11-22-33-44-55   dynamic
        # *nix:    ? (192.168.1.10) at 00:11:22:33:44:55 on en0 [ether]
        ip = mac = None
        if "(" in line and ") at " in line:
            # *nix format
            try:
                ip = line.split("(")[1].split(")")[0]
                mac = line.split(") at ")[1].split()[0]
            except Exception:
                pass
        else:
            # Windows format (columns)
            cols = [c for c in line.split() if c]
            if len(cols) >= 2 and cols[0][0].isdigit():
                ip, mac = cols[0], cols[1].replace("-", ":")
        if ip and mac and mac.lower() != "ff:ff:ff:ff:ff:ff":
            pairs.append((ip, mac.lower()))
    return pairs

def _scan_fallback(cidr: str, limit_hosts: int = 256) -> List[Host]:
    """Ping a few hosts in the /24 and then read ARP table (non-admin friendly)."""
    net = ipaddress.ip_network(cidr, strict=False)
    # Throttle to first 256 hosts to avoid long scans on huge nets
    targets = [str(ip) for ip in net.hosts()]
    if len(targets) > limit_hosts:
        targets = targets[:limit_hosts]
    # Best-effort nudge of ARP cache
    for ip in targets:
        _ping(ip, timeout_ms=250)
    pairs = _read_arp_table()
    hosts = [Host(ip=ip, mac=mac, hostname=_reverse_dns(ip)) for ip, mac in pairs]
    # Keep only IPs inside our net
    return [h for h in hosts if ipaddress.ip_address(h.ip) in net]

def scan_subnet(subnet: Optional[str] = None, timeout: int = 3) -> List[Dict[str, str]]:
    """
    Returns list of {'ip','mac','hostname'}.
    Uses Scapy when possible; else pings and scrapes ARP table.
    """
    ip = _default_ipv4()
    cidr = subnet or ( _derive_cidr(ip) if ip else "192.168.1.0/24" )
    hosts: List[Host] = []
    if _SCAPY_OK:
        # Tweak Scapy to be quieter on Windows
        try:
            conf.verb = 0  # type: ignore
        except Exception:
            pass
        hosts = _scan_scapy(cidr, timeout=timeout)
    if not hosts:
        hosts = _scan_fallback(cidr)
    # Deduplicate by IP
    uniq: Dict[str, Host] = {h.ip: h for h in hosts}
    return [ {"ip":h.ip, "mac":h.mac, "hostname":h.hostname} for h in uniq.values() ]

def run() -> str:
    # Respect environment hint: IGRIS_SUBNET=10.0.0.0/24
    hint = os.environ.get("IGRIS_SUBNET") or None
    results = scan_subnet(hint)
    if not results:
        msg = ("No hosts discovered.\n"
               "- If on Windows, install Npcap (WinPcap compatible mode) for Scapy.\n"
               "- Ensure you are on a real LAN (not a host-only adapter).\n"
               "- Try running with elevated privileges for raw sockets.")
        return msg
    # Pretty table
    header = "Discovered Devices:\nIP Address        MAC Address          Hostname"
    lines = [header, "-"*len(header)]
    for d in sorted(results, key=lambda x: list(map(int, x["ip"].split(".")))):
        lines.append(f"{d['ip']:<16}  {d['mac']:<18}  {d['hostname']}")
    return "\n".join(lines)
