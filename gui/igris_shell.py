import tkinter as tk
import json
import time
import subprocess
import threading
from pathlib import Path

# A.1: Add imports and a simple registry of actions
import re
import speech_recognition as sr
from tkinter import ttk, font as tkfont

# This registry maps human-readable names to internal command actions.
# It will power the command palette.
SHELL_COMMANDS = {
    "List Running Containers": "app:list",
    "List Open Windows": "window:list",
    "Tile Windows": "window:tile",
    "Toggle Fullscreen": "window:fullscreen",
    "Open Calculator": "app:calc",
    "Show System Stats Widget": "widget:add name=system_stats",
    "Show Network Stats Widget": "widget:add name=network_stats",
    "Quit Igris Shell": "shell:quit",
}

# --- Configuration ---
ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "ai_assistant_config"
CONFIG_DIR = ROOT / "ai_assistant_config"
COMMAND_QUEUE_FILE = CONFIG_DIR / "desktop_command_queue.json"
COMMAND_QUEUE_LOCK = threading.Lock()

class IgrisShell:
    def __init__(self, root):
        self.root = root
        self.root.title("Igris Desktop Shell")
        self.root.geometry("800x600")

        self.root.configure(bg="#1e1e1e")

        # A simple label to show that the shell is running
        tk.Label(
            self.root,
            text="Igris Shell Active",
            font=("Segoe UI", 24, "bold"),
            fg="lightgreen",
            bg="#1e1e1e"
        ).pack(pady=50)

        # A.2: Inside IgrisShell.__init__, add hotkeys and a help overlay
        # --- Command Palette & Hotkeys ---
        self.command_palette_visible = False
        self.actions = SHELL_COMMANDS
        self.root.bind_all("<Control-space>", self.show_command_palette)
        self.root.bind_all("<F1>", self.toggle_help_overlay)
        self.root.bind_all("<Control-grave>", lambda e: self.dispatch_command("window:fullscreen"))

        # --- Voice Input ---
        if sr is not None:
            try:
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
                self.adjust_for_ambient_noise()
            except Exception as e:
                print(f"Error initializing voice recognition: {e}")
                self.recognizer = self.microphone = None

        # --- Help Overlay ---
        self.help_overlay = tk.Frame(self.root, bg="black", highlightbackground="grey", highlightthickness=1)
        help_font = tkfont.Font(family="Consolas", size=10)
        help_text = """
--- Igris Shell Hotkeys ---

Ctrl+Space   -  Open Command Palette
F1           -  Toggle this help overlay
Ctrl+`       -  Toggle Fullscreen
"""
        tk.Label(
            self.help_overlay,
            text=help_text.strip(),
            fg="lightgreen",
            bg="black",
            font=help_font,
            justify=tk.LEFT,
        ).pack(padx=20, pady=20)
        self.help_overlay.place(relx=0.5, rely=0.5, anchor=tk.CENTER, bordermode="outside")
        self.help_overlay.lower() # Start hidden
        self.help_visible = False

        # --- Fullscreen state ---
        self._is_fullscreen = False

        # --- IPC command queue poller ---
        self.poll_command_queue()

    def poll_command_queue(self):
        """Periodically check the command queue file for new commands."""
        with COMMAND_QUEUE_LOCK:
            if COMMAND_QUEUE_FILE.exists():
                try:
                    queue = json.loads(COMMAND_QUEUE_FILE.read_text(encoding="utf-8"))
                    if queue:
                        for command_data in queue:
                            action = command_data.get("action", "")
                            params = command_data.get("params", {})
                            # A simple way to pass params for now
                            param_str = " ".join([f"{k}={v}" for k, v in params.items()])
                            full_command = f"{action} {param_str}".strip()
                            self.dispatch_command(full_command)
                        # Clear the queue after processing
                        COMMAND_QUEUE_FILE.write_text("[]", encoding="utf-8")
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Error processing command queue: {e}")
        # Poll again after 1 second
        self.root.after(1000, self.poll_command_queue)

    def dispatch_command(self, command_action):
        """Handles commands from the queue and the command palette."""
        # Log every dispatch for debugging
        print(f"[IgrisShell] Dispatching: {command_action}")
        # Fullscreen toggle
        if command_action == "window:fullscreen":
            self.toggle_fullscreen()
        # Quit shell
        elif command_action == "shell:quit":
            self.quit_shell()
        # Widget commands
        elif command_action.startswith("widget:"):
            self.handle_widget_command(command_action)
        # Application commands
        elif command_action.startswith("app:"):
            self.handle_app_command(command_action)
        # Plugin commands
        elif command_action.startswith("plugin:"):
            self.run_plugin_action(command_action)
        # Unknown commands
        else:
            # If an unknown command is issued, surface it to the UI
            self.show_feedback(f"[Shell] Unknown command: {command_action}")

    def handle_widget_command(self, command_action):
            print("Widget Command: ", command_action)
            tk.Label(self.root, text=f"Widget Command: {command_action}", fg="white", bg="#1e1e1e").pack()

    def handle_app_command(self, command_action):
            print("App Command: ", command_action)

            tk.Label(self.root, text=f"Executed: {command_action}", fg="white", bg="#1e1e1e").pack()

    def run_plugin_action(self, action):
        """
        Executes a plugin command specified as ``plugin:<plugin_name>``.

        The plugin should be a Python file located in the ``plugins``
        directory under the Igris project root. The plugin will be
        executed in a subprocess using the current Python interpreter.

        On success, the plugin's standard output will be displayed in the
        shell. On failure or if the plugin is not found, an error
        message will be shown via ``show_feedback``.
        """
        import subprocess
        import sys
        import shlex

        # Remove the "plugin:" prefix and strip whitespace
        plugin_name = action.replace("plugin:", "", 1).strip()
        # Determine the root directory of the project. This file lives in
        # ``gui`` or ``shell``; the root is two directories up.
        ROOT_DIR = Path(__file__).resolve().parent.parent
        script_path = ROOT_DIR / "plugins" / f"{plugin_name}.py"

        # If the plugin does not exist, show an error
        if not script_path.exists():
            self.show_feedback(f"[Plugin Error] {plugin_name}.py not found.")
            return

        # Build the subprocess call. Use sys.executable to ensure the
        # same Python interpreter executes the plugin.
        cmd = [sys.executable, str(script_path)]

        try:
            # Run the plugin with a timeout. Capture both stdout and
            # stderr so we can surface errors if they occur. A 60s
            # timeout prevents hanging indefinitely.
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(ROOT_DIR),
                timeout=60
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                # If the plugin exited with a non-zero code, surface the
                # error output.
                error_output = result.stderr.strip() or "Unknown error"
                self.show_feedback(f"[Plugin Error] {plugin_name} failed:\n{error_output}")
            else:
                # On success, display the output or a message if none
                display_output = output if output else "No output returned."
                self.show_feedback(f"[Plugin Output]\n{display_output}")
        except Exception as e:
            # Catch and display any unexpected runtime errors
            self.show_feedback(f"[Runtime Error] {e}")

    def show_feedback(self, message):
        """
        Display a feedback message in the shell UI. The message
        appears as a transient label that auto-dismisses after a
        short duration. This method ensures consistent styling and
        centralized message handling.
        """
        # Create a label to hold the feedback message
        label = tk.Label(
            self.root,
            text=message,
            justify="left",
            anchor="w",
            fg="lightblue",
            bg="#1e1e1e",
            font=("Consolas", 10)
        )
        # Pack it at the top of the window so it appears underneath
        # any existing content
        label.pack(fill=tk.X, padx=10, pady=(2, 2))
        # Schedule it to be destroyed after 10 seconds
        self.root.after(10000, label.destroy)

    def toggle_fullscreen(self, event=None):
        self._is_fullscreen = not self._is_fullscreen
        self.root.attributes("-fullscreen", self._is_fullscreen)

    # A.3: Add the palette + helpers as methods on IgrisShell
    def toggle_help_overlay(self, event=None):
        """Toggles the visibility of the F1 help overlay."""
        if self.help_visible:
            self.help_overlay.lower()
        else:
            self.help_overlay.lift()
        self.help_visible = not self.help_visible

    def show_command_palette(self, event=None):
        """Creates and displays the command palette."""
        if self.command_palette_visible:
            return
        self.command_palette_visible = True

        # --- Palette Window ---
        self.palette = tk.Toplevel(self.root)
        self.palette.overrideredirect(True)
        self.palette.geometry("500x300")
        # Center it on the screen
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 250
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 150
        self.palette.geometry(f"+{x}+{y}")
        self.palette.transient(self.root)
        self.palette.grab_set()

        # --- Styling ---
        style = ttk.Style(self.palette)
        style.configure("Command.TEntry", foreground="white", background="#333", insertbackground="white", fieldbackground="#333")

        # --- Entry Widget ---
        self.palette_entry_var = tk.StringVar()
        entry = ttk.Entry(self.palette, textvariable=self.palette_entry_var, style="Command.TEntry", font=("Segoe UI", 12))
        entry.pack(fill=tk.X, padx=5, pady=5)
        entry.focus_set()
        entry.grab_set() # Ensure focus is grabbed
        self.palette_entry_var.trace_add("write", self.filter_palette)

        # --- Listbox for Actions ---
        self.palette_listbox = tk.Listbox(self.palette, bg="#222", fg="white", selectbackground="#0078D7",
                                          highlightthickness=0, borderwidth=0, font=("Segoe UI", 10), activestyle='none')
        self.palette_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.populate_palette_listbox()

        # --- Bindings ---
        self.palette.bind("<Escape>", self.hide_command_palette)
        entry.bind("<Return>", self.execute_palette_selection)
        entry.bind("<Up>", lambda e: self.navigate_palette(-1))
        entry.bind("<Down>", lambda e: self.navigate_palette(1))
        self.palette_listbox.bind("<Button-1>", self.execute_palette_selection)
        self.palette_listbox.bind("<Double-1>", self.execute_palette_selection)

    def hide_command_palette(self, event=None):
        """Destroys the command palette window."""
        if not self.command_palette_visible:
            return
        self.palette.destroy()
        self.command_palette_visible = False

    def populate_palette_listbox(self, items=None):
        """Clears and populates the listbox with a given set of items."""
        self.palette_listbox.delete(0, tk.END)
        if items is None:
            items = sorted(self.actions.keys())
        for item in items:
            self.palette_listbox.insert(tk.END, item)
        if self.palette_listbox.size() > 0:
            self.palette_listbox.selection_set(0)

    def filter_palette(self, *args):
        """Filters the command palette listbox based on user input."""
        query = self.palette_entry_var.get().lower()
        if not query:
            self.populate_palette_listbox()
            return
        
        filtered_items = [
            name for name in self.actions
            if re.search(query, name, re.IGNORECASE)
        ]
        self.populate_palette_listbox(sorted(filtered_items))

    def navigate_palette(self, direction):
        """Handles up/down arrow navigation in the command palette."""
        if not self.palette_listbox.size():
            return
        current_selection = self.palette_listbox.curselection()
        current_index = current_selection[0] if current_selection else -1
        
        new_index = (current_index + direction) % self.palette_listbox.size()
        
        self.palette_listbox.selection_clear(0, tk.END)
        self.palette_listbox.selection_set(new_index)
        self.palette_listbox.activate(new_index)
        self.palette_listbox.see(new_index)

    def execute_palette_selection(self, event=None):
        """Executes the selected command from the palette."""
        selection_indices = self.palette_listbox.curselection()
        if not selection_indices:
            return
        
        selected_action_name = self.palette_listbox.get(selection_indices[0])
        command_action = self.actions.get(selected_action_name)
        
        if command_action:
            self.dispatch_command(command_action)
        

    def quit_shell(self):
        self.root.quit()
        self.hide_command_palette()


if __name__ == "__main__":
    root = tk.Tk()
    app = IgrisShell(root)
    root.mainloop()


# TODO:
# Wire setup_voice_input.py into shell on startup.
# Auto-load task intents from task_intents.json into the shell dispatcher.