"""
Application Launcher for Igris OS (Phase 5)
- Consolidates all Docker container management logic.
- Interacts with the WindowManager to display containerized apps.
"""
import os
import tkinter as tk
from tkinter import scrolledtext
import threading

try:
    from file_browser_app import FileBrowserApp
    NATIVE_APPS = {"file_browser": FileBrowserApp}
except ImportError:
    NATIVE_APPS = {}

try:
    import docker
    from docker.errors import DockerException, NotFound
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

class AppLauncher:
    """A centralized class for managing Docker container applications."""

    def __init__(self, window_manager):
        """
        Initializes the AppLauncher.

        Args:
            window_manager: An instance of the WindowManager, or None for CLI mode.
        """
        self.wm = window_manager
        self.client = None
        self.interactive_sessions = {} # Maps app_name to container object

        if not DOCKER_AVAILABLE:
            print("[AppLauncher] Docker library not found. Container features disabled.")
            return
        try:
            self.client = docker.from_env()
            self.client.ping()
            print("[AppLauncher] Docker client connected successfully.")
        except DockerException:
            self.client = None
            print("[AppLauncher] Docker daemon not running. Container features disabled.")

    def launch(self, image_name="hello-world", app_name=None, interactive=False, native=False):
        """
        Launches a container or a native app. Dispatches to the correct method.
        """
        if native:
            return self.launch_native_app(app_name)

        if not self.client:
            return "[ERROR] Docker is not available to launch apps."
        if not self.wm:
            return "[ERROR] Cannot launch a GUI app without a Window Manager."

        if interactive:
            return self._launch_interactive(image_name, app_name)
        else:
            return self._launch_batch(image_name, app_name)

    def launch_native_app(self, app_name):
        """Launches a native Tkinter application in a new window."""
        if not self.wm:
            return "[ERROR] Cannot launch a native app without a Window Manager."

        app_class = NATIVE_APPS.get(app_name)
        if not app_class:
            return f"[ERROR] Native application '{app_name}' not found."

        window = self.wm.create_window(app_name=app_name)
        if not window:
            return f"[ERROR] Could not create window for {app_name}."

        window.geometry("600x400")
        app_instance = app_class(window)
        return f"Launched native app '{app_name}' in a new window."

    def _launch_batch(self, image_name, app_name=None):
        """Launches a non-interactive container and displays its output."""
        if app_name is None:
            app_name = image_name.split(':')[0]

        window = self.wm.create_window(app_name=app_name)
        if not window:
            return f"[ERROR] Could not create window for {app_name}."

        log_area = scrolledtext.ScrolledText(window, wrap=tk.WORD, bg="#111", fg="white", font=("Consolas", 10))
        log_area.pack(expand=True, fill=tk.BOTH)
        log_area.insert(tk.END, f"Starting container '{image_name}'...\n\n")

        def _run_and_stream_logs():
            try:
                container_output = self.client.containers.run(image_name, detach=False, remove=True)
                logs = container_output.decode('utf-8')
                if window.winfo_exists():
                    window.after(0, lambda: log_area.insert(tk.END, logs))
                    window.after(0, lambda: log_area.insert(tk.END, "\n\n--- Container exited ---"))
            except Exception as e:
                if window.winfo_exists():
                    window.after(0, lambda: log_area.insert(tk.END, f"\n[ERROR] {e}"))

        threading.Thread(target=_run_and_stream_logs, daemon=True).start()
        return f"Launched batch app '{app_name}' in a new window."

    def _launch_interactive(self, image_name, app_name=None):
        """Launches an interactive container with a terminal-like window."""
        if app_name is None:
            # Generate a unique name to avoid conflicts
            app_name = f"{image_name.split(':')[0]}-term-{os.urandom(2).hex()}"

        if app_name in self.interactive_sessions:
            self.wm.focus_window(app_name)
            return f"Interactive session '{app_name}' is already running."

        def on_close():
            self.cleanup_interactive_session(app_name)

        window = self.wm.create_window(app_name=app_name, on_close_callback=on_close)
        window.geometry("700x500")

        term_widget = scrolledtext.ScrolledText(window, wrap=tk.WORD, bg="#111", fg="white", font=("Consolas", 10), insertbackground="white")
        term_widget.pack(expand=True, fill=tk.BOTH)

        try:
            container = self.client.containers.create(
                image_name,
                stdin_open=True, tty=True, detach=True, name=app_name,
                command="/bin/sh" # Use a standard shell
            )
            container.start()
            sock = container.attach_socket(params={'stdin': 1, 'stdout': 1, 'stderr': 1, 'stream': 1})
            self.interactive_sessions[app_name] = (container, sock)

            # Start a thread to read from the container's output
            threading.Thread(target=self._stream_reader, args=(sock, term_widget, app_name), daemon=True).start()

            # Bind user input from the terminal widget to the container's input
            term_widget.bind("<Return>", lambda event, s=sock: self._send_to_container(event.widget, s))

            return f"Launched interactive session '{app_name}'."
        except Exception as e:
            self.wm.destroy_window(app_name)
            return f"[ERROR] Failed to launch interactive session: {e}"

    def _stream_reader(self, sock, widget, app_name):
        """Reads from a container's socket and writes to the terminal widget."""
        try:
            while True:
                output = sock.recv(1024)
                if not output: break
                if widget.winfo_exists():
                    widget.after(0, widget.insert, tk.END, output.decode('utf-8', 'replace'))
                    widget.after(0, widget.see, tk.END)
        except Exception:
            pass # Socket was likely closed
        finally:
            if widget.winfo_exists():
                widget.after(0, widget.insert, tk.END, f"\n\n--- Session '{app_name}' disconnected ---")

    def _send_to_container(self, widget, sock):
        """Sends the last line of user input from the widget to the container."""
        # Get the content of the line the cursor is on
        command = widget.get("insert linestart", "insert").strip() + "\n"
        sock.sendall(command.encode('utf-8'))

    def cleanup_interactive_session(self, app_name):
        """Stops and removes the container associated with an interactive session."""
        if app_name in self.interactive_sessions:
            container, sock = self.interactive_sessions.pop(app_name)
            print(f"[AppLauncher] Cleaning up session for '{app_name}'...")
            try:
                sock.close()
                container.stop(timeout=2)
                container.remove(force=True)
            except Exception as e:
                print(f"[AppLauncher] Error during cleanup for '{app_name}': {e}")
        # The window itself is destroyed by the WindowManager
        self.wm.destroy_window(app_name)

    def list_running_containers(self):
        """Returns a list of running container objects."""
        if not self.client:
            return []
        try:
            return self.client.containers.list()
        except Exception:
            return []