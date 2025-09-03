"""
Remove Docker Container Plugin (Phase 5)
- Lists stopped containers and allows the user to remove them individually.
- Provides an option to prune all stopped containers.
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
    Lists stopped containers and prompts the user to select one to remove,
    or to prune all stopped containers.
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

    # Filter for containers that are 'exited' or 'created'
    stopped_containers = client.containers.list(
        all=True, filters={'status': ['exited', 'created']}
    )

    if not stopped_containers:
        return "No stopped containers found to remove."

    while True:
        print("\n--- Remove a Stopped Docker Container ---")
        for i, container in enumerate(stopped_containers):
            image_tag = container.image.tags[0] if container.image.tags else 'N/A'
            print(f"{i + 1}. ID: {container.short_id:<12} Name: {container.name:<25} Image: {image_tag}")

        print("\nEnter the number of the container to remove, 'p' to prune all, or 'q' to quit.")
        choice = input("Selection: ").strip().lower()

        if choice == 'q':
            return "Container removal operation cancelled."

        if choice == 'p':
            confirm = input("Are you sure you want to remove ALL stopped containers? (y/n): ").lower()
            if confirm == 'y':
                pruned_info = client.containers.prune()
                reclaimed_space = pruned_info.get('SpaceReclaimed', 0)
                return f"[SUCCESS] Pruned all stopped containers. Reclaimed space: {reclaimed_space} bytes."
            else:
                print("Prune operation cancelled.")
                continue

        try:
            index = int(choice) - 1
            if 0 <= index < len(stopped_containers):
                container_to_remove = stopped_containers[index]
                print(f"[INFO] Removing container '{container_to_remove.name}' ({container_to_remove.short_id})...")
                container_to_remove.remove()
                return f"[SUCCESS] Container '{container_to_remove.name}' removed successfully."
            else:
                print("[ERROR] Invalid selection. Please try again.")
        except ValueError:
            print("[ERROR] Invalid input. Please enter a number, 'p', or 'q'.")
        except NotFound:
             return "[ERROR] Container not found. It may have already been removed."

if __name__ == "__main__":
    print(run())