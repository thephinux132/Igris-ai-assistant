# Igris User Manual

**Version:** 2.0.0
**Platform:** Windows 10/11, WSL

---

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Getting Started](#getting-started)
4. [Authentication](#authentication)
5. [Voice Commands](#voice-commands)
6. [Command Reference](#command-reference)
7. [Plugins](#plugins)
8. [Configuration](#configuration)
9. [Security Features](#security-features)
10. [Troubleshooting](#troubleshooting)

---

## Introduction

Igris is a local AI-powered system control assistant for Windows and WSL. It provides:

- **Voice Control**: Hands-free system operation
- **Natural Language**: Describe tasks in plain English
- **Smart Suggestions**: Learns your patterns and anticipates needs
- **Security First**: Approval gates for sensitive operations
- **Offline Capable**: Works without internet (with local LLM)

### Key Features

| Feature | Description |
|---------|-------------|
| Voice Input | Wake word activation, speech recognition |
| NL Parser | Natural language to command translation |
| Predictive | Learns usage patterns, suggests actions |
| Secure | Windows Hello, PIN auth, command approval |
| Extensible | Plugin system for custom functionality |

---

## Installation

### Prerequisites

- Windows 10/11 or WSL2
- Python 3.10+
- Microphone (for voice features)

### Quick Install

```bash
# Clone repository
git clone https://github.com/thephinux132/Igris-ai-assistant
cd Igris-ai-assistant

# Install dependencies
pip install -r config/requirements.txt

# Run setup
python setup.py
```

Optional Components

```bash
# Voice recognition
pip install SpeechRecognition pyaudio

# Local LLM (Ollama)
# Download from: https://ollama.ai
ollama pull llama3.2:3b

# Windows Hello support
pip install winrt-Windows.Security.Credentials.UI
```

---

## Getting Started

### First Run

1. Launch Igris:
   ```bash
   python cli/igris_cli.py
   ```
2. Set up authentication:
   - Enter a PIN when prompted
   - Optionally configure Windows Hello
3. Try a command:
   ```text
   > open notepad
   ```

### Basic Usage

**Text Commands:**
```text
> open chrome
> what time is it
> show system status
> list files in downloads
```

**Voice Commands:**
1. Say "Hey Igris" (wake word)
2. Wait for acknowledgment
3. Speak your command

---

## Authentication

Igris uses multi-factor authentication for security.

### PIN Authentication

- Required for admin operations
- Rate-limited: 5 attempts, then 5-minute lockout
- Stored securely in Windows Credential Manager

Setting PIN:
```text
> igris --set-pin
Enter new PIN: ****
Confirm PIN: ****
PIN updated successfully
```

### Windows Hello (Optional)

If configured, biometric authentication is preferred:

- Fingerprint
- Face recognition
- Falls back to PIN if unavailable

### Approval Gates

Dangerous commands require explicit approval:

```text
⚠️  APPROVAL REQUIRED (CRITICAL)
==================================================
Command: shutdown /s /t 0
Action:  System shutdown requested
==================================================

Type 'CONFIRM CRITICAL' to approve:
>
```

---

## Voice Commands

### Wake Words

Default wake words:
- "Igris"
- "Hey Igris"
- "Okay Igris"

### Supported Commands

| Say | Action |
|-----|--------|
| "Open notepad" | Launch Notepad |
| "Open chrome" | Launch Chrome browser |
| "Lock computer" | Lock screen |
| "What time is it" | Show current time |
| "System status" | Show system info |
| "Battery level" | Show battery status |
| "Shutdown" | Shutdown (requires approval) |
| "Restart" | Restart (requires approval) |

### Voice Settings

Edit `config/voice_commands.yaml`:

```yaml
settings:
  language: "en-US"
  timeout: 5
  energy_threshold: 300
```

---

## Command Reference

### System Commands

| Command | Description | Approval |
|---------|-------------|----------|
| `open <app>` | Launch application | No |
| `lock` | Lock screen | No |
| `sleep` | Enter sleep mode | No |
| `shutdown` | Shutdown system | Yes |
| `restart` | Restart system | Yes |

### Query Commands

| Command | Description |
|---------|-------------|
| `status` | System overview |
| `time` | Current time |
| `battery` | Battery level |
| `disk` | Disk usage |
| `memory` | RAM usage |
| `network` | Network status |

### File Commands

| Command | Description |
|---------|-------------|
| `list <path>` | List directory |
| `open <path>` | Open file/folder |
| `create folder <name>` | Create directory |

---

## Plugins

Igris supports plugins for extended functionality.

### Available Plugins

| Plugin | Description |
|--------|-------------|
| `network_scanner` | Scan local network |
| `task_scheduler` | Manage scheduled tasks |
| `ssh_tunnel` | Create SSH tunnels |
| `system_hardening` | Security hardening |

### Using Plugins

```text
> plugin list
> plugin run network_scanner
> plugin info task_scheduler
```

### Creating Plugins

See `docs/PLUGIN_DEVELOPMENT.md` for plugin development guide.

---

## Configuration

### Main Configuration

`config/settings.yaml`:

```yaml
workspace_root: "~"
log_level: "INFO"
approval_mode: "strict"
allowed_paths:
  - "~/Documents"
  - "~/Downloads"
```

### Voice Configuration

`config/voice_commands.yaml` - Wake words and command mappings

### Approval Rules

`config/approval_rules.yaml` - Command approval policies

---

## Security Features

### Defense Layers

1. **Input Validation**: All inputs sanitized
2. **Command Whitelist**: Only approved commands
3. **Approval Gates**: Dangerous ops require consent
4. **Rate Limiting**: Brute-force protection
5. **Secure Storage**: Credentials encrypted

### Security Best Practices

- Use Windows Hello when available
- Review approval prompts carefully
- Keep Igris updated
- Don't disable security features

### Audit Logging

All security events logged to:
`logs/security_audit.log`

---

## Troubleshooting

### Voice Not Working

1. Check microphone permissions
2. Verify PyAudio installed:
   ```bash
   pip install pyaudio
   ```
3. Test microphone:
   ```bash
   python -c "import speech_recognition as sr; print(sr.Microphone.list_microphone_names())"
   ```

### Ollama Not Connecting

1. Verify Ollama running:
   ```bash
   curl http://localhost:11434/api/tags
   ```
2. Pull required model:
   ```bash
   ollama pull llama3.2:3b
   ```

### Authentication Locked

After 5 failed attempts, wait 5 minutes or:
```bash
python -c "from core.secure_auth import AuthenticationManager; AuthenticationManager().reset_lockout()"
```

### Command Blocked

If a command is blocked:
1. Check `logs/security_audit.log` for reason
2. Verify command doesn't contain shell metacharacters
3. Request approval if required

---

## Getting Help

- **Issues**: https://github.com/thephinux132/Igris-ai-assistant/issues
- **Docs**: `docs/` directory
- **Command**: `igris --help`

---

**Last Updated**: 2026-01-11
