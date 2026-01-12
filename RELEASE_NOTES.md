# Igris AI Assistant v2.0.0

**Release Date:** 2026-01-11
**Codename:** Fortress

---

## Overview

Igris v2.0.0 is a complete security overhaul and feature expansion of the AI-powered system control assistant. This release transforms Igris into an enterprise-ready solution with defense-in-depth security, cross-platform support, and modern deployment options.

---

## Highlights

### Security Hardening
- **41 vulnerabilities remediated** - All command injection points secured
- **Multi-factor authentication** - Hardware keys, biometrics, and PIN support
- **Encrypted audit logs** - Tamper-evident with chain verification
- **Approval workflows** - Configurable gates for dangerous operations

### New Capabilities
- **Voice Control** - Natural speech recognition with wake word detection
- **AI Integration** - Local LLM support via Ollama for natural language parsing
- **Smart Predictions** - Learns your patterns and suggests relevant actions
- **Remote API** - Secure REST endpoints for remote management

### Platform Expansion
- **Linux** - Full systemd integration, Secret Service storage
- **macOS** - launchd service, Keychain, Touch ID support
- **Docker** - Production-ready containerization
- **Standalone** - PyInstaller executables for all platforms

---

## Installation

### Quick Start (Python)
```bash
git clone https://github.com/thephinux132/Igris-ai-assistant
cd Igris-ai-assistant
pip install -r config/requirements.txt
python cli/igris_cli.py
```

### Linux

```bash
./scripts/install_linux.sh
systemctl --user start igris
```

### macOS

```bash
./scripts/install_macos.sh
launchctl start com.igris.assistant
```

### Docker

```bash
docker-compose up -d
```

---

## Breaking Changes

### Authentication

- Simulated fingerprint/voice authentication removed
- Users must re-enter PIN on first run (automatic migration)
- Rate limiting now enforced (5 attempts, 5-min lockout)

### API Changes

- `run_cmd()` now requires list input, not string
- New security modules must be imported for secure execution
- Plugin loading validates paths strictly

See `BREAKING_CHANGES.md` for migration guide.

---

## Security Advisories

This release addresses the following security issues:
| ID | Severity | Description |
|---|---|---|
| IGRIS-2026-001 | CRITICAL | Command injection via shell=True |
| IGRIS-2026-002 | CRITICAL | Plaintext credential storage |
| IGRIS-2026-003 | HIGH | Simulated authentication bypass |
| IGRIS-2026-004 | HIGH | Path traversal in plugin loader |
| IGRIS-2026-005 | MEDIUM | Missing input validation |

All issues have been fully remediated in this release.

---

## System Requirements

| Platform | Minimum | Recommended |
|---|---|---|
| Python | 3.10 | 3.11+ |
| RAM | 256 MB | 512 MB |
| Disk | 100 MB | 500 MB |
| OS | Windows 10, Ubuntu 20.04, macOS 11 | Latest |

### Optional Dependencies

- **Voice:** `SpeechRecognition`, `PyAudio`
- **LLM:** Ollama with `llama3.2:3b` model
- **Hardware Keys:** `fido2` library
- **Biometrics:** `pyobjc` (macOS), `winrt` (Windows)

---

## What's Next

Planned for future releases:
- Web dashboard interface
- Mobile companion app
- Cloud sync (encrypted)
- Plugin marketplace

---

## Contributors

- Security hardening and architecture by Claude Code (Anthropic)
- Original Igris concept and implementation by project maintainers

---

## Links

- **Documentation:** `docs/USER_MANUAL.md`
- **Security Policy:** `docs/SECURITY.md`
- **Issue Tracker:** https://github.com/thephinux132/Igris-ai-assistant/issues

---

**Thank you for using Igris!**
