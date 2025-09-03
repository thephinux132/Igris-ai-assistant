"""
List Docker Containers Plugin (Phase 5)
- Lists all running Docker containers with key information.
- Requires the 'docker' library and a running Docker daemon.
"""

try:
    import docker
    from docker.errors import DockerException
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

def run():
    """
    Connects to Docker and lists running containers.
    """
    if not DOCKER_AVAILABLE:
        return ("[ERROR] The 'docker' library is not installed. "
                "Please run: pip install docker")

    try:
        client = docker.from_env()
        # Check if Docker is running
        client.ping()
    except DockerException:
        return ("[ERROR] Docker daemon is not running.\n"
                "Please start Docker Desktop and try again.")

    try:
        containers = client.containers.list()
        if not containers:
            return "No Docker containers are currently running."

        report = ["Running Docker Containers:"]
        report.append("--------------------------------------------------------------------------------")
        report.append(f"{'ID':<12} {'Name':<25} {'Image':<20} {'Status':<15} {'Ports':<15}")
        report.append("--------------------------------------------------------------------------------")
        for container in containers:
            ports = ", ".join([f"{p.public_port}->{p.private_port}/{p.ip}" for p in container.ports.values() if p.public_port])
            report.append(f"{container.short_id:<12} {container.name:<25} {container.image.tags[0] if container.image.tags else 'N/A':<20} {container.status:<15} {ports:<15}")
        report.append("--------------------------------------------------------------------------------")
        return "\n".join(report)
    except Exception as e:
        return f"[ERROR] Failed to list Docker containers: {e}"

if __name__ == "__main__":
    print(run())