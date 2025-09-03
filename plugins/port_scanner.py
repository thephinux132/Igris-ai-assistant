"""
Port Scanner Plugin (Hardened, Concurrent, Non-Interactive)
- Target: from env IGRIS_TARGET (hostname or IP). If unset, falls back to local host IP.
- Ports:  from env IGRIS_PORTS (e.g., "1-1024,3389,8080"). Default: 20-1024.
- Returns a printable string table (no prompts, safe for GUI worker threads).
"""
from __future__ import annotations
import os, socket, ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable, List, Tuple

DEFAULT_RANGE = "20-1024"
CONNECT_TIMEOUT = 0.25
MAX_WORKERS = 128

SERVICE_HINTS = {
    20: "FTP-DATA", 21: "FTP", 22: "SSH", 23: "TELNET", 25: "SMTP",
    53: "DNS", 67: "DHCP", 68: "DHCP", 69: "TFTP", 80: "HTTP",
    110: "POP3", 111: "RPCbind", 123: "NTP", 135: "MSRPC", 137: "NBNS",
    139: "NetBIOS-SSN", 143: "IMAP", 161: "SNMP", 389: "LDAP",
    443: "HTTPS", 445: "SMB", 465: "SMTPS", 587: "SMTP-Sub",
    993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1521: "Oracle",
    1723: "PPTP", 2049: "NFS", 2375: "Docker", 2376: "Docker TLS",
    3000: "Dev/App", 3306: "MySQL", 3389: "RDP", 5432: "Postgres",
    5900: "VNC", 6379: "Redis", 8000: "HTTP-Alt", 8080: "HTTP-Alt",
    8443: "HTTPS-Alt", 9000: "Dev", 9200: "Elasticsearch",
}

def _default_ipv4() -> str:
    # Robust local IPv4 discovery (no external traffic sent)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())

def _parse_ports(spec: str) -> List[int]:
    """Parse '1-1024,3389,8080' → sorted unique ints."""
    ports = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            a, b = int(a), int(b)
            if a > b:
                a, b = b, a
            for p in range(max(1, a), min(65535, b) + 1):
                ports.add(p)
        else:
            p = int(chunk)
            if 1 <= p <= 65535:
                ports.add(p)
    return sorted(ports)

def _resolve_target(s: str) -> Tuple[str, str]:
    """Return (hostname_or_ip_input, resolved_ipv4)."""
    s = s.strip()
    try:
        # If already IPv4, normalize
        ip = ipaddress.ip_address(s)
        if isinstance(ip, ipaddress.IPv4Address):
            return s, str(ip)
    except Exception:
        pass
    # Resolve hostname → IPv4
    resolved = socket.gethostbyname(s)
    return s, resolved

def _try_connect(ip: str, port: int, timeout: float) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((ip, port)) == 0
    except Exception:
        return False

def _fmt_table(target_in: str, ip: str, open_ports: List[int]) -> str:
    if not open_ports:
        return f"No open ports found on {target_in} ({ip}) in selected range."
    lines = [f"Open ports on {target_in} ({ip}):", "PORT   SERVICE", "----   -------"]
    for p in open_ports:
        lines.append(f"{p:<6} {SERVICE_HINTS.get(p, '')}")
    # Single line summary as well
    lines.append("")
    lines.append("List: " + ", ".join(map(str, open_ports)))
    return "\n".join(lines)

def run() -> str:
    # Inputs
    target_spec = os.environ.get("IGRIS_TARGET", "").strip() or _default_ipv4()
    port_spec = os.environ.get("IGRIS_PORTS", DEFAULT_RANGE)

    try:
        target_in, ip = _resolve_target(target_spec)
    except Exception as e:
        return f"[port_scanner] Target resolution failed for '{target_spec}': {e}"

    try:
        ports = _parse_ports(port_spec)
        if not ports:
            ports = _parse_ports(DEFAULT_RANGE)
    except Exception:
        ports = _parse_ports(DEFAULT_RANGE)

    # Concurrent scan
    open_ports: List[int] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_try_connect, ip, p, CONNECT_TIMEOUT): p for p in ports}
        for fut in as_completed(futs):
            p = futs[fut]
            try:
                if fut.result():
                    open_ports.append(p)
            except Exception:
                pass

    open_ports.sort()
    return _fmt_table(target_in, ip, open_ports)
