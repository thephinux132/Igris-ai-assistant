"""Convert Services Scanner - Mock Vulnerability Check"""
def run():
    weak_services = ["telnet", "ftp", "rsh"]
    return "Weak Services Detected:\n" + "\n".join(weak_services)