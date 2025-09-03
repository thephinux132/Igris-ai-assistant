# Igris OS - Modular Desktop Environment Design Document

## 1. Vision & Objective

The goal is to evolve Igris from a command-line/single-GUI application into a fully-fledged, voice-first desktop environment. In this environment, applications run as isolated containers, and all user interactions—launching apps, managing windows, and accessing system information—are primarily handled through voice commands. This creates a secure, modular, and highly intuitive computing experience.

## 2. Core Architectural Components

1.  **Igris Shell (`igris_shell.py`)**:
    -   **Role**: The root of the visual environment. This will be the new main entry point for the desktop mode.
    -   **Function**: A persistent, fullscreen Tkinter application that serves as the desktop background. It will be responsible for managing a simple taskbar/dock, desktop widgets, and acting as the parent container for all application windows. It will replace the direct launch of `igris_control_gui...` when in desktop mode.

2.  **Window Manager (`window_manager.py`)**:
    -   **Role**: Manages the lifecycle and placement of all application windows.
    -   **Function**: A non-GUI module that provides an API for creating, destroying, positioning (e.g., tiling, cascading), and focusing windows within the Igris Shell. Each window will be a `Toplevel` or `Frame` widget that hosts the output of a containerized application.

3.  **Application Launcher (`app_launcher.py`)**:
    -   **Role**: The bridge between intents and running applications.
    -   **Function**: An evolution of the existing Docker plugins (`run_containerized_app.py`, etc.). This module will be responsible for:
        -   Starting a requested application in its Docker container.
        -   Communicating with the `Window Manager` to create a window for the application.
        -   Piping the container's standard input/output to the GUI window.

4.  **Voice & Intent Core (Enhancement)**:
    -   **Role**: The primary user input mechanism.
    -   **Function**: The existing voice recognition and intent matching system will be expanded to understand desktop-oriented commands.
        -   **Examples**: "Igris, open a terminal on the left side", "Show me my running apps", "Close the web browser", "Maximize the code editor".
        -   These intents will be routed to the appropriate components (`Application Launcher`, `Window Manager`).

5.  **Widget System (`widget_manager.py`)**:
    -   **Role**: Manages small, persistent informational views on the desktop.
    -   **Function**: A system to place and manage simple widgets (e.g., clock, calendar, system status) directly on the Igris Shell desktop. This builds upon the concept of `add_calendar_widget.py`.

## 3. Example Interaction Flow: "Igris, open a terminal."

1.  The user speaks the command.
2.  The **Voice & Intent Core** captures the audio, transcribes it, and matches it to a `launch_app` intent with the parameter `app_name: "terminal"`.
3.  The intent is dispatched to the **Application Launcher**.
4.  The **Application Launcher** executes the logic to start the pre-configured "terminal" Docker container.
5.  The **Application Launcher** then calls the **Window Manager**: `window_manager.create_window(app_name="terminal", container_id=...)`.
6.  The **Window Manager** creates a new `Toplevel` window within the **Igris Shell**.
7.  The **Application Launcher** redirects the terminal container's stdin/stdout/stderr streams to a `scrolledtext` widget inside the new window.
8.  The **Igris Shell** now displays the new, interactive terminal window on the desktop.

## 4. Implementation Plan

1.  **Step 1: Create the Igris Shell.**
    -   Create a new main entry point, `igris_shell.py`.
    -   Initially, it will be a simple, blank, fullscreen window that can be launched via a new plugin/command. This establishes the foundation.
2.  **Step 2: Develop the Window Manager.**
    -   Create `window_manager.py` with placeholder functions like `create_window()` and `destroy_window()`.
    -   Integrate it with the Igris Shell so the shell can own and manage a list of windows.
3.  **Step 3: Refactor Container Launchers.**
    -   Consolidate the logic from `run_containerized_app.py`, `list_docker_containers.py`, etc., into a unified `app_launcher.py` module.
    -   Modify it to interact with the `Window Manager` instead of just printing to the console.
4.  **Step 4: Expand Voice Intents.**
    -   Add new tasks to `task_intents_gui_tags.json` for window management and app launching.
    -   Update the core intent matching logic to handle these new commands.

---