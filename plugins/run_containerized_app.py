"""
Run Containerized App Plugin (Phase 5 Proof-of-Concept)
- Demonstrates running a simple application inside a Docker container.
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
    Pulls and runs the 'hello-world' Docker container and returns its output.
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

    container_name = "hello-world"
    print(f"[INFO] Pulling and running container: '{container_name}'...")

    try:
        output = client.containers.run(container_name, remove=True)
        return f"[SUCCESS] Container '{container_name}' ran successfully:\n\n{output.decode('utf-8')}"
    except Exception as e:
        return f"[ERROR] Failed to run container '{container_name}':\n{e}"

if __name__ == "__main__":
    print(run())