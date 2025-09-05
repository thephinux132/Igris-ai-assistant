# Phase 5: Igris OS – Full Desktop Environment

- **Voice-Activated, Modular Desktop**
  - Launchable shell (`igris_shell.py`) as a full-screen environment.
  - Voice and text parity for system commands.
  - Modular design: windows, widgets, and plugins can be added or removed live.

- **Containerized App Runner**
  - Launch and manage Dockerized applications from the desktop.
  - Support interactive terminals, native apps, and sandboxed services.
  - App Manager CLI + GUI for monitoring and lifecycle control.

- **Personalization & UI/UX**
  - Taskbar with live app indicators.
  - Customizable themes (Dark, Light, Solarized, Monokai).
  - Window opacity control and saved preferences in `ai_script_policy.json`.

- **Plugin Ecosystem**
  - Plugins load dynamically from `/plugins`.
  - Tools menu with grouped plugin launcher.
  - Autorun support: define which plugins run at startup.
  - Plugin execution logger for auditing.

- **Memory & Context Awareness**
  - Centralized conversation memory manager.
  - GUI tool for browsing, editing, and clearing history.
  - Anticipatory suggestion engine based on usage patterns.

- **Integrated Security Layer**
  - Fingerprint → PIN → Voice verification pipeline for privileged tasks.
  - Policy-driven admin enforcement toggle (fingerprint_required).
  - Daily checkup plugin: auto-run system health checks with logging.

- **Networking Intelligence**
  - Built-in dashboards for LAN sweep, port scans, and active connections.
  - Visual topology maps rendered inside the desktop shell.
  - SSH tunnel manager for secure remote connections.

- **Persistence & Logging**
  - Chat export/import for record keeping.
  - AI system log + plugin execution logs.
  - Historical script storage under `ai_script_history`.

- **User Experience Enhancements**
  - Alias system (`/alias`) to shorten commands.
  - Slash commands (`/history`, `/clear`, `/intent`).
  - Text-to-speech responses optional via toggle.
  - Suggestions bar for next-step automation hints.

