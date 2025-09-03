"""
Window Manager for Igris OS Desktop Environment (Phase 5)
- Manages the lifecycle and placement of application windows.
"""
import tkinter as tk

class WindowManager:
    """Manages Toplevel windows within the Igris Shell."""
    def __init__(self, shell_root):
        self.shell = shell_root
        self.windows = {}  # Maps app_name to Toplevel window instance
        self._window_count = 0
        self.taskbar = None

    def set_taskbar(self, taskbar_instance):
        """Allows the shell to register the taskbar for callbacks."""
        self.taskbar = taskbar_instance

    def create_window(self, app_name="Untitled App", on_close_callback=None):
        """Creates and manages a new application window."""
        # To avoid name collisions for multiple untitled apps
        if app_name == "Untitled App":
            self._window_count += 1
            unique_name = f"{app_name} {self._window_count}"
        else:
            unique_name = app_name

        if unique_name in self.windows:
            print(f"[WindowManager] Window for '{unique_name}' already exists. Focusing.")
            self.windows[unique_name].lift()
            return self.windows[unique_name]

        window = tk.Toplevel(self.shell)
        window.title(unique_name)
        window.geometry("400x300+100+100") # Set initial size and position

        # If a custom on_close is provided, use it. Otherwise, just destroy the window.
        # This allows the AppLauncher to hook into the close event for container cleanup.
        if on_close_callback and callable(on_close_callback):
            window.protocol("WM_DELETE_WINDOW", on_close_callback)
        else:
            window.protocol("WM_DELETE_WINDOW", lambda name=unique_name: self.destroy_window(name))

        if self.taskbar:
            # Bind focus events to update the taskbar's active state indicator
            window.bind("<FocusIn>", lambda e, name=unique_name: self.taskbar.set_active_app(name))

        self.windows[unique_name] = window
        if self.taskbar:
            self.taskbar.add_app(unique_name)

        print(f"[WindowManager] Created window for '{unique_name}'.")
        return window

    def destroy_window(self, app_name):
        """Finds a managed window by name and destroys it."""
        window = self.windows.pop(app_name, None)
        if window:
            if self.taskbar:
                self.taskbar.remove_app(app_name)
            print(f"[WindowManager] Destroying window for '{app_name}'.")
            window.destroy()
        else:
            print(f"[WindowManager] No window found for '{app_name}' to destroy.")

    def close_active_window(self):
        """Closes the currently focused Toplevel window."""
        active_window = self.shell.focus_get()
        # Ensure the focused widget is a Toplevel window managed by us
        if active_window and isinstance(active_window, tk.Toplevel):
            for name, window_instance in self.windows.items():
                if window_instance == active_window:
                    self.destroy_window(name)
                    return f"Closed active window: {name}"
        return "No active application window to close."

    def get_active_window_name(self):
        """Returns the name of the currently focused Toplevel window, if managed."""
        active_window = self.shell.focus_get()
        if active_window and isinstance(active_window, tk.Toplevel):
            for name, window_instance in self.windows.items():
                if window_instance == active_window:
                    return name
        return None

    def focus_window(self, app_name):
        """Brings the specified window to the front."""
        window = self.windows.get(app_name)
        if window:
            window.lift()
            window.focus_force()

    def tile_windows(self):
        """Arranges all open windows in a simple tile layout."""
        num_windows = len(self.windows)
        if num_windows == 0:
            return "No windows to tile."

        screen_width = self.shell.winfo_screenwidth()
        screen_height = self.shell.winfo_screenheight()

        cols = int(num_windows**0.5)
        rows = (num_windows + cols - 1) // cols

        win_width = screen_width // cols
        win_height = (screen_height - 30) // rows # Adjust for taskbar if any

        for i, window in enumerate(self.windows.values()):
            row, col = divmod(i, cols)
            x, y = col * win_width, row * win_height
            window.geometry(f"{win_width}x{win_height}+{x}+{y}")

        return f"Tiled {num_windows} windows."

    def list_windows(self):
        """Returns a list of currently managed window names."""
        return list(self.windows.keys())