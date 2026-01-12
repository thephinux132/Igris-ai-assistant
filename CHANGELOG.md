# Changelog

All notable changes to Igris AI Assistant will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-01-11

### Added

#### Security Infrastructure
- **Secure Execution Engine**: Command execution without `shell=True` vulnerabilities
- **Secrets Manager**: Platform-native credential storage (Windows Credential Manager, macOS Keychain, Linux Secret Service)
- **Multi-Factor Authentication**: PIN (Argon2id), Windows Hello, Touch ID, YubiKey/FIDO2
- **Input Validation**: 5-layer defense against injection attacks
- **Approval Workflow**: YAML-configurable gates for dangerous commands
- **Encrypted Audit Logs**: Tamper-evident logging with chain verification
- **Rate Limiting**: Brute-force protection (5 attempts, 5-min lockout)

#### User Experience
- **Voice Commands**: Wake word detection, speech recognition integration
- **Natural Language Parser**: Ollama LLM integration with pattern fallback
- **Predictive Engine**: Time/frequency/sequence-based task suggestions
- **User Manual**: Comprehensive documentation

#### Enterprise Features
- **REST API**: Secure remote management with API key authentication
- **Hardware Key Support**: YubiKey and FIDO2 authenticator integration
- **TLS Support**: Optional HTTPS for API server

#### Platform Support
- **Linux**: systemd service, libsecret/keyring storage, DE detection
- **macOS**: launchd service, Keychain storage, Touch ID
- **Windows**: Native credential manager, Windows Hello
- **Docker**: Multi-stage build, docker-compose with optional Ollama

#### Development Infrastructure
- **CI/CD Pipeline**: GitHub Actions with matrix testing
- **Pre-commit Hooks**: Security scanning on commit
- **Static Analysis**: Bandit and Semgrep integration
- **PyInstaller Build**: Cross-platform standalone executables

### Changed
- Command execution now uses list-based subprocess calls
- Authentication flow prioritizes strongest available method
- Plugin loading validates paths against traversal attacks

### Removed
- Simulated fingerprint authentication (security theater)
- Simulated voice authentication (security theater)
- Unprotected `shell=True` in main code paths

### Security
- Fixed 41 command injection vulnerabilities
- Migrated credentials from plaintext to encrypted storage
- Added path traversal protection to plugin loader
- Implemented LLM output sanitization

### Fixed
- All high-risk plugins secured (schtasks, SSH, nmap)
- GUI files updated with secure execution fallback

## [1.0.0] - Previous

Initial release (pre-security hardening).
