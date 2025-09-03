"""
proactive_context_agent.py

An intelligent agent that runs in the background to understand user activity.
It periodically captures the screen when the user is active, uses a multimodal
LLM to determine the user's current context (e.g., 'CODING', 'BROWSING'),
and logs this context for use by other parts of the Igris system, like the
suggestion engine.

This version is optimized to only perform analysis when user activity is
detected, saving system resources.
"""
import time
import threading
from pathlib import Path

# --- Core Igris Imports ---
# Assuming the main GUI application has set up sys.path correctly.
try:
    from core.igris_core import ask_ollama_with_image
    from plugins import screen_capture
    from core.memory_manager import add_memory
except ImportError as e:
    print(f"[ERROR] ProactiveContextAgent: Failed to import core modules: {e}")
    ask_ollama_with_image = None
    screen_capture = None
    add_memory = None

# --- Activity Monitoring Imports ---
try:
    from pynput import mouse, keyboard
except ImportError:
    print("[ERROR] ProactiveContextAgent: `pynput` is not installed. Activity monitoring is disabled.")
    print("          Please run: pip install pynput")
    mouse = None
    keyboard = None


class ProactiveContextAgent:
    """
    A background agent that monitors user activity and logs their context.
    Uses a singleton pattern to ensure only one instance runs.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self):
        # Prevent re-initialization
        if hasattr(self, '_initialized') and self._initialized:
            return

        # --- Agent Configuration ---
        self.idle_threshold_seconds = 300  # 5 minutes
        self.check_interval_seconds = 60   # 1 minute

        # --- State for Activity Tracking ---
        self.last_activity_time = time.time()
        self.activity_lock = threading.Lock()
        self.agent_thread = None
        self.stop_agent_flag = threading.Event()

        # --- Listener Setup ---
        self.mouse_listener = mouse.Listener(on_move=self._on_activity, on_click=self._on_activity, on_scroll=self._on_activity) if mouse else None
        self.keyboard_listener = keyboard.Listener(on_press=self._on_activity) if keyboard else None
        self._initialized = True

    def _on_activity(self, *args, **kwargs):
        """Callback function to update the last activity timestamp."""
        with self.activity_lock:
            self.last_activity_time = time.time()

    def _start_activity_listeners(self):
        """Starts the mouse and keyboard listeners in the background."""
        if self.mouse_listener and not self.mouse_listener.is_alive():
            self.mouse_listener.start()
        if self.keyboard_listener and not self.keyboard_listener.is_alive():
            self.keyboard_listener.start()

    def _stop_activity_listeners(self):
        """Stops the mouse and keyboard listeners."""
        if self.mouse_listener and self.mouse_listener.is_alive():
            self.mouse_listener.stop()
        if self.keyboard_listener and self.keyboard_listener.is_alive():
            self.keyboard_listener.stop()

    def _analyze_and_log_context(self):
        """
        Captures the screen, sends it to the LLM for analysis, and logs the result.
        """
        if not all([screen_capture, ask_ollama_with_image, add_memory]):
            print("[AGENT] Core functions not available. Skipping analysis.")
            return

        print("[AGENT] User is active. Capturing screen for context analysis...")
        image_path = None
        try:
            # Assuming screen_capture.run can return a path
            image_path_obj = screen_capture.run(return_path=True)
            if not image_path_obj or "[ERROR]" in str(image_path_obj):
                print(f"[AGENT] Screen capture failed: {image_path_obj}")
                return
            image_path = Path(image_path_obj)

            prompt = "Analyze this screenshot and determine the user's primary activity. Respond with a single-word context like 'CODING', 'BROWSING', 'READING', 'GAMING', 'WRITING', or 'IDLE'."
            response_data = ask_ollama_with_image(prompt, str(image_path))
            analysis_result = response_data.get("response", "UNKNOWN").strip().upper()
            context = analysis_result.split()[0]
            print(f"[AGENT] Determined user context: {context}")

            memory_entry = {"type": "user_context", "context": context, "source": "proactive_context_agent"}
            add_memory(memory_entry)

        except Exception as e:
            print(f"[AGENT] An error occurred during context analysis: {e}")
        finally:
            if image_path and image_path.exists():
                try:
                    image_path.unlink()
                except OSError as e:
                    print(f"[AGENT] Failed to delete temp screenshot {image_path}: {e}")

    def _agent_loop(self):
        """The main loop for the proactive agent."""
        print("[AGENT] Proactive Context Agent is running.")
        self._start_activity_listeners()

        while not self.stop_agent_flag.is_set():
            with self.activity_lock:
                idle_time = time.time() - self.last_activity_time
            
            if idle_time < self.idle_threshold_seconds:
                self._analyze_and_log_context()
            else:
                print(f"[AGENT] User is idle. (Idle for {idle_time:.0f}s)")
            
            self.stop_agent_flag.wait(self.check_interval_seconds)

        self._stop_activity_listeners()
        print("[AGENT] Proactive Context Agent has stopped.")

    def start(self):
        """Starts the agent thread."""
        if self.agent_thread and self.agent_thread.is_alive():
            return "[INFO] Proactive context agent is already running."
        self.stop_agent_flag.clear()
        self.agent_thread = threading.Thread(target=self._agent_loop, daemon=True)
        self.agent_thread.start()
        return "[SUCCESS] Proactive context agent started."

    def stop(self):
        """Stops the agent thread."""
        if not self.agent_thread or not self.agent_thread.is_alive():
            return "[INFO] Proactive context agent is not running."
        self.stop_agent_flag.set()
        return "[SUCCESS] Proactive context agent stopping."

# --- Plugin Entry Point ---
_agent_instance = None

def run(action="start", *args):
    """
    Entry point for the Igris plugin system.
    Manages the lifecycle of the ProactiveContextAgent.
    
    :param action: "start" or "stop"
    """
    global _agent_instance
    if not mouse or not keyboard:
        return "[ERROR] `pynput` library not found. Agent cannot start."
    
    if _agent_instance is None:
        _agent_instance = ProactiveContextAgent()

    if action == "start":
        return _agent_instance.start()
    elif action == "stop":
        return _agent_instance.stop()
    else:
        return f"[ERROR] Unknown action '{action}'. Use 'start' or 'stop'."