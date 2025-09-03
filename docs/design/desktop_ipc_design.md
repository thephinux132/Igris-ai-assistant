# Igris Desktop - GUI-to-Shell IPC Design

## 1. Objective

To create a reliable, one-way communication channel allowing the main Igris Control GUI to send commands to the running Igris Shell process. This enables voice or text commands entered in the main GUI to control the desktop environment (e.g., launch applications, manage windows).

## 2. Architecture: File-Based Command Queue

We will use a simple file-based queue for Inter-Process Communication (IPC). This approach is robust, easy to debug, and avoids the complexities of sockets or shared memory management within a Tkinter environment.

1.  **Command Queue File**: A dedicated file, `desktop_command_queue.json`, will be created in the `ai_assistant_config` directory. This file will act as the "mailbox" between the two processes.

2.  **Command Structure**: Commands will be written to the queue as a list of JSON objects. Each object will contain:
    -   `timestamp`: A precise `datetime.now().isoformat()` string to uniquely identify the command and ensure chronological processing.
    -   `action`: The command to be executed (e.g., `desktop:launch_app`).
    -   `params`: A dictionary of parameters for the command (e.g., `{"image_name": "ubuntu:latest"}`).

    **Example `desktop_command_queue.json` content:**
    ```json
    [
      {
        "timestamp": "2023-10-27T10:00:01.123456",
        "action": "desktop:launch_app",
        "params": { "image_name": "hello-world" }
      },
      {
        "timestamp": "2023-10-27T10:00:05.789012",
        "action": "desktop:tile_windows",
        "params": {}
      }
    ]
    ```

## 3. Component Responsibilities

### Igris Control GUI (`igris_control_gui...py`) - The Sender

-   When a user command results in an action prefixed with `desktop:`, the GUI will **not** execute it directly.
-   Instead, it will read the existing `desktop_command_queue.json`, append the new command object to the list, and write the file back. This operation must be thread-safe if accessed from multiple threads.
-   It will then display a confirmation to the user, e.g., `[Desktop] Command 'launch_app' sent to Igris Shell.`.

### Igris Shell (`igris_shell.py`) - The Receiver

-   The shell will contain a `poll_command_queue` method.
-   This method will be scheduled to run periodically using `self.after(500, self.poll_command_queue)` (e.g., every 500ms).
-   Inside the polling method, it will:
    1.  Read the `desktop_command_queue.json` file.
    2.  If the file is not empty, it will process each command in the list.
    3.  For each command, it will dispatch the action and parameters to the appropriate internal component (e.g., `self.app_launcher.launch(**params)`).
    4.  After processing all commands, it will **clear the file** by writing an empty list `[]` to it, marking the queue as empty.

## 4. Implementation Plan

1.  **Modify the Main GUI**: Update the `_execute_task` or a similar command-handling function to check for the `desktop:` prefix. If found, it should write to the command queue file instead of calling `run_cmd`.
2.  **Implement Polling in Igris Shell**: Add the `poll_command_queue` method to the `IgrisShell` class and start the polling loop in its `__init__` method.
3.  **Implement Command Dispatching in Igris Shell**: Create a dispatching mechanism within the shell to call the correct `WindowManager` or `AppLauncher` methods based on the `action` string from the queue.
4.  **Enhance `AppLauncher` and `WindowManager`**: Add the necessary methods (e.g., `tile_windows` in the `WindowManager`) to handle the new desktop intents.