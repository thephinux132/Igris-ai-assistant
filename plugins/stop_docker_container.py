"""
Stop Docker Container Plugin (Phase 5)
- Lists running containers and allows the user to stop one.
- Requires the 'docker' library and a running Docker daemon.
"""

try:
    import docker
    from docker.errors import DockerException, NotFound
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

def run():
    """
    Lists running containers and prompts the user to select one to stop.
    """
    if not DOCKER_AVAILABLE:
        return ("[ERROR] The 'docker' library is not installed. "
                "Please run: pip install docker")

    try:
        client = docker.from_env()
        client.ping()
    except DockerException:
        return ("[ERROR] Docker daemon is not running.\n"
                "Please start Docker Desktop and try again.")

    containers = client.containers.list()
    if not containers:
        return "No containers are currently running to stop."

    while True:
        print("\n--- Stop a Running Docker Container ---")
        for i, container in enumerate(containers):
            print(f"{i + 1}. ID: {container.short_id:<12} Name: {container.name:<25} Image: {container.image.tags[0] if container.image.tags else 'N/A'}")

        print("\nEnter the number of the container to stop, or 'q' to quit.")
        choice = input("Selection: ").strip().lower()

        if choice == 'q':
            return "Container stop operation cancelled."

        try:
            index = int(choice) - 1
            if 0 <= index < len(containers):
                container_to_stop = containers[index]
                print(f"[INFO] Stopping container '{container_to_stop.name}' ({container_to_stop.short_id})...")
                try:
                    container_to_stop.stop()
                    return f"[SUCCESS] Container '{container_to_stop.name}' stopped successfully."
                except Exception as e:
                    return f"[ERROR] Failed to stop container: {e}"
            else:
                print("[ERROR] Invalid selection. Please try again.")
        except ValueError:
            print("[ERROR] Invalid input. Please enter a number or 'q'.")
        except NotFound:
             return "[ERROR] Container not found. It may have already been stopped."


if __name__ == "__main__":
    print(run())