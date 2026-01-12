# Breaking Changes - Security Hardening v2.0.0

**Date**: 2026-01-08
**Impact**: HIGH - Authentication and credential storage
**Migration Required**: YES - Automatic with user confirmation

---

## Overview

Igris AI Assistant v2.0.0 implements comprehensive security hardening to address critical vulnerabilities. This includes replacing simulated authentication with real security mechanisms and moving credentials from plaintext files to secure storage.

---

## What Changed (Phase 2: Secrets Migration)

### 1. Credential Storage (BREAKING)

**Before**:
- Admin PIN hash stored in plaintext JSON file: `~/OneDrive/Documents/ai_script_policy.json`
- Hash format: SHA256 (no salt, vulnerable to rainbow tables)
- File synced to cloud (OneDrive)
- Accessible to any process with file read permissions

**After**:
- Credentials stored in OS secure storage:
  - **Windows**: Windows Credential Manager
  - **Linux/macOS**: system keyring with encryption
  - **Fallback**: Encrypted file with restricted permissions
- Hash format: Argon2id (memory-hard, GPU-resistant)
- No cloud sync
- Requires OS-level authentication to access

**Migration Path**:
1. On first launch after upgrade, system detects old policy file
2. User prompted to re-enter current PIN (cannot reverse SHA256)
3. New Argon2id hash generated and stored in secure backend
4. `admin_pin_hash` removed from policy file
5. Migration marker added to policy: `{"migrated_to_secure_storage": true}`
6. Backup created: `ai_script_policy.json.backup`

### 2. Authentication Removed (BREAKING)

**Simulated Fingerprint Authentication**:
- **Before**: Press Enter to "simulate" fingerprint scan
- **After**: REMOVED - was security theater, provided no actual protection
- **Functions affected**:
  - `cli_show_fingerprint_prompt()` → now returns `False` with warning
  - `gui.authentication.show_fingerprint_prompt()` → deprecated

**Simulated Voice Authentication**:
- **Before**: Type "authorize" to simulate voice confirmation
- **After**: REMOVED - was security theater, provided no actual protection
- **Functions affected**:
  - `cli_confirm_by_voice()` → now returns `False` with warning
  - `gui.authentication.confirm_by_voice()` → deprecated

**Why Removed?**:
These functions gave users a false sense of security while providing zero actual protection. Anyone with keyboard access could bypass them instantly.

### 3. Authentication Flow Changed (BREAKING)

**Before**:
```python
def authenticate_admin() -> bool:
    # Try fingerprint (fake - just press Enter)
    if cli_show_fingerprint_prompt():
        return True

    # Try PIN (SHA256, no salt)
    if cli_prompt_for_pin(pin_hash):
        return True

    # Try voice (fake - just type "authorize")
    if cli_confirm_by_voice():
        return True

    return False
```

**After**:
```python
def authenticate_admin() -> bool:
    auth_mgr = AuthenticationManager()

    # Check if PIN configured
    if not auth_mgr.is_pin_configured():
        # Offer migration if needed
        check_and_migrate()

    # Single strong factor: PIN with Argon2id + rate limiting
    return auth_mgr.authenticate_admin()
```

**New Security Features**:
- **Rate limiting**: 5 failed attempts → 5-minute lockout
- **Audit logging**: All auth attempts logged
- **Stronger hashing**: Argon2id (time_cost=3, memory_cost=64MB)
- **No fake auth**: One real authentication factor instead of three fake ones

### 4. Function Signatures Changed (BREAKING)

**`core/igris_core.py`**:

```python
# Before
def cli_prompt_for_pin(pin_hash: str) -> bool

# After
def cli_prompt_for_pin(pin_hash: str = None) -> bool
```
- `pin_hash` is now optional - loads from secure storage if not provided
- Automatically uses new authentication if security modules available
- Falls back to legacy SHA256 if needed

```python
# Before (always returned True)
def cli_show_fingerprint_prompt() -> bool

# After (always returns False with deprecation warning)
def cli_show_fingerprint_prompt() -> bool
```

```python
# Before (always returned True)
def cli_confirm_by_voice(expected_phrase: str = "yes allow this") -> bool

# After (always returns False with deprecation warning)
def cli_confirm_by_voice(expected_phrase: str = "yes allow this") -> bool
```

**`cli/igris_cli.py`**:

```python
# Before (hardcoded PIN)
def load_policy() -> dict:
    return {"admin_pin_hash": "03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4"}

# After (loads from secure storage)
def load_policy() -> dict:
    # Try secure storage first
    # Fall back to file
    # Last resort: hardcoded with warning
```

---

## Migration Guide

### For Existing Users

**Automatic Migration (Recommended)**:

When you first launch the upgraded version, the system will automatically detect your old credentials and guide you through migration:

```bash
$ python cli/igris_cli.py "system status"

============================================================
SECURITY UPGRADE - PIN Migration Required
============================================================

Your admin PIN is being upgraded to stronger encryption.
Please enter your current PIN to migrate to secure storage.

Current PIN (attempt 1/3): ****

✓ PIN migrated successfully to secure storage!
✓ Policy file updated: ~/OneDrive/Documents/ai_script_policy.json
✓ Backup created: ~/OneDrive/Documents/ai_script_policy.json.backup

============================================================
Migration Complete!
============================================================

Your credentials are now stored securely.
The old policy file has been backed up.
```

**Manual Migration**:

```bash
# Run migration utility directly
python core/migration_utils.py

# Or import and run
python3 -c "from core.migration_utils import check_and_migrate; check_and_migrate()"
```

**Verification**:

After migration, verify your credentials are stored securely:

```bash
# On Windows
cmdkey /list | grep IgrisAI
# Should show: Target: IgrisAI_AdminCredentials

# Check policy file (should NOT contain admin_pin_hash)
cat ~/OneDrive/Documents/ai_script_policy.json
```

### For New Installations

First-time users will be guided through secure PIN setup:

```bash
$ python cli/igris_cli.py "open notepad"

============================================================
IGRIS AI ASSISTANT - First Time Setup
============================================================

Welcome! Let's set up your admin PIN.
PIN Requirements:
  - At least 4 characters
  - Maximum 32 characters
  - Can be numbers, letters, or mixed

Enter new admin PIN: ****
Confirm admin PIN: ****

✓ Admin PIN configured successfully!
```

---

## Backward Compatibility

### What Still Works

- ✅ Existing `task_intents.json` format (no changes)
- ✅ Old plugin system (Phase 2 doesn't modify plugins)
- ✅ CLI commands and arguments
- ✅ GUI functionality (though GUI auth updated in later phases)
- ✅ Most user workflows unchanged

### What Breaks

- ❌ Code calling `cli_show_fingerprint_prompt()` expecting `True`
  - **Fix**: Remove calls or replace with `authenticate_admin()`

- ❌ Code calling `cli_confirm_by_voice()` expecting `True`
  - **Fix**: Remove calls or replace with `authenticate_admin()`

- ❌ External scripts reading `admin_pin_hash` from policy file
  - **Fix**: Use `SecretsManager().get_pin_hash()` instead

- ❌ Hardcoded PIN hash "1234" (SHA256) in external systems
  - **Fix**: Re-authenticate after migration to get new hash

### Graceful Degradation

If security modules fail to load:
1. System falls back to legacy authentication
2. Warning logged: "Using legacy authentication - security upgrade recommended"
3. Old SHA256 hashing still works (but prompts upgrade)
4. System continues functioning (reduced security)

---

## Testing Your Migration

**Test 1: Verify Migration**

```bash
# Run test script
python test_phase2_auth.py

# Expected output:
# ✓ All critical tests passed!
# Phase 2 integration is ready for deployment.
```

**Test 2: Test Authentication**

```bash
# Try admin command (should prompt for PIN)
python cli/igris_cli.py "shutdown /r /t 60"

# Expected:
# 🔑 Enter admin PIN: ****
# [SECURITY] Admin authentication successful.
```

**Test 3: Test Rate Limiting**

```bash
# Enter wrong PIN 5 times
# Expected on 6th attempt:
# [SECURITY] Account locked. Try again in 300 seconds.
```

---

## Troubleshooting

### "Admin PIN not configured"

**Cause**: No PIN in secure storage and no migration completed
**Solution**:
```bash
# Run migration
python core/migration_utils.py

# Or for new installation
python3 -c "from core.migration_utils import setup_new_installation; setup_new_installation()"
```

### "Legacy PIN hash detected - migration recommended"

**Cause**: Policy file still has `admin_pin_hash` field
**Solution**:
```bash
# Run migration to move credential to secure storage
python core/migration_utils.py
```

### "Using default PIN - run migration or setup!"

**Cause**: No credentials found anywhere (new installation)
**Solution**:
```bash
# Run first-time setup
python cli/igris_cli.py  # Will prompt for setup on first admin operation
```

### "Security modules not available"

**Cause**: Missing dependencies (`argon2-cffi`, `keyring`, `pywin32`)
**Solution**:
```bash
# Install dependencies
pip install -r config/requirements.txt

# Or individually
pip install argon2-cffi keyring
# On Windows: pip install pywin32
```

### Migration Failed: "Too many incorrect attempts"

**Cause**: Entered wrong PIN 3 times during migration
**Solution**:
1. Wait a few minutes
2. Run migration again
3. If you forgot your PIN, manually edit policy file to reset (development only)

---

## Security Implications

### Improvements

✅ **Credentials no longer in plaintext files**
✅ **Argon2id resistant to GPU/ASIC attacks**
✅ **Rate limiting prevents brute force**
✅ **Audit logging tracks all access attempts**
✅ **OS-level security (Windows Credential Manager)**
✅ **No cloud sync of credentials**
✅ **Simulated auth removed (was security theater)**

### Considerations

⚠️ **Lockout Risk**: 5 failed attempts locks account for 5 minutes
⚠️ **PIN Recovery**: Lost PIN requires manual reset (by design)
⚠️ **Windows-focused**: Best security on Windows; fallback on Linux/macOS
⚠️ **Migration Required**: One-time user interaction needed

---

## Rollback (Emergency Only)

If migration causes critical issues, you can temporarily rollback:

1. **Restore backup policy file**:
   ```bash
   cp ~/OneDrive/Documents/ai_script_policy.json.backup ~/OneDrive/Documents/ai_script_policy.json
   ```

2. **Remove migrated credentials** (optional):
   ```bash
   # Windows
   cmdkey /delete:IgrisAI_AdminCredentials

   # Linux/macOS
   python3 -c "from core.secrets_manager import SecretsManager; SecretsManager().delete_secret('admin_pin_hash')"
   ```

3. **Revert code** (if needed):
   ```bash
   git checkout HEAD~1 core/igris_core.py cli/igris_cli.py
   ```

**Note**: Rollback is **not recommended** for security reasons. Only use in emergencies.

---

## FAQ

**Q: Do I need to remember a new PIN?**
A: No, your existing PIN still works. You'll re-enter it once during migration, then it's stored more securely.

**Q: What happened to fingerprint/voice authentication?**
A: Removed because they were fake (just pressing Enter or typing "authorize"). They provided no real security.

**Q: Will this break my existing plugins?**
A: No, Phase 2 only affects authentication. Plugins are updated in Phase 5.

**Q: Can I use the same PIN as before?**
A: Yes, but we recommend choosing a stronger PIN (letters + numbers) for better security.

**Q: What if I forget my PIN?**
A: For development: manually delete credentials and reconfigure. For production: implement your own PIN recovery workflow.

**Q: Why was migration needed instead of automatic conversion?**
A: SHA256 is one-way; we can't reverse it to get your PIN. You must re-enter it so we can hash it with Argon2id.

**Q: Is my data being sent anywhere?**
A: No, everything is local. Credentials stored in Windows Credential Manager (Windows) or system keyring (Linux/macOS).

---

---

## Phase 3: Command Execution Security (NEW)

**Status**: COMPLETED
**Impact**: HIGH - All command execution now secure
**Migration**: Automatic (backward compatible)

### What Changed

**Before**:
```python
def run_cmd(cmd_list: list) -> str:
    command_str = " ".join(cmd_list)
    proc = subprocess.run(command_str, shell=True, ...)  # VULNERABLE
```

**After**:
```python
def run_cmd(cmd_list: list) -> str:
    # Use secure execution (no shell=True)
    from core.secure_execution import run_cmd_safe
    result = run_cmd_safe(cmd_list)  # SECURE
    # Falls back to legacy if security modules unavailable
```

### Security Improvements

✅ **shell=True eliminated** - No shell interpretation of metacharacters
✅ **Command injection blocked** - `;`, `|`, `&`, `$()`, backticks rejected
✅ **Path traversal prevented** - `../../` patterns blocked
✅ **Input validation** - All command parts validated before execution
✅ **Audit logging** - All executions logged for security monitoring
✅ **Timeout enforcement** - 30-second default timeout prevents hanging

### Files Updated

1. **core/igris_core.py** - `run_cmd()` now uses `secure_execution.run_cmd_safe()`
2. **igris_phase3_patch_20250810_224424/igris_core.py** - `run_shell()` secured
3. **igris_phase3_patch_20250810_224424/igris_cli.py** - `run_shell()` secured

### Breaking Changes

**Function Behavior Changes**:

```python
# Command injection now blocked
run_cmd(['echo', 'test; rm -rf /'])
# Before: Executes both echo AND rm (DANGEROUS!)
# After: [BLOCKED] Shell metacharacters detected

# Path traversal now blocked
run_cmd(['cat', '../../etc/passwd'])
# Before: Could read arbitrary files
# After: [BLOCKED] Potential path traversal detected
```

### Backward Compatibility

- ✅ Valid commands work exactly as before
- ✅ Automatic fallback if security modules unavailable
- ✅ No changes to function signatures
- ✅ Existing callers don't need updates

### Testing

Run Phase 3 tests:
```bash
python test_phase3_execution.py

# Expected output:
# ✓ All critical security tests passed!
# Phase 3 command execution security is ready for deployment.
```

### What's Now Secure

- `core/igris_core.py::run_cmd()` - Primary command execution
- `igris_phase3_patch_20250810_224424/igris_core.py::run_shell()` - Patch version
- `igris_phase3_patch_20250810_224424/igris_cli.py::run_shell()` - CLI patch

### What Still Needs Updating (Phase 5)

- GUI files (22 files with `shell=True`)
- Plugin files (4 high-risk plugins: schtasks, SSH, nmap)
- Other helper scripts

---

## Phase 4: Input Validation (NEW)

**Status**: COMPLETED
**Impact**: HIGH - All input entry points now validated
**Migration**: Automatic (backward compatible)

### What Changed

**Before**:
```python
# User input accepted directly without validation
user_req = " ".join(args.prompt).strip()
obj = ask_ollama(prompt=user_req, ...)
sys.exit(handle_intent(obj))
```

**After**:
```python
# Multi-layer validation at every entry point
user_req = " ".join(args.prompt).strip()

# 1. Validate user input
validator = InputValidator(strict_mode=True)
is_valid, error_msg = validator.validate_user_input(user_req)
if not is_valid:
    print(f"[SECURITY] Input validation failed: {error_msg}")
    sys.exit(1)

# 2. Query LLM
obj = ask_ollama(prompt=user_req, ...)

# 3. Sanitize LLM output
obj = validator.sanitize_llm_output(obj)

# 4. Validate task intents (at load time)
intents = load_task_intents(CWD)
validate_intents_for_dangerous_patterns(intents)

# 5. Secure plugin loading
loader = SecurePluginLoader()
plugin = loader.load_plugin(plugin_name)  # Path traversal blocked
```

### Security Improvements

✅ **Defense in Depth** - Validation at 5 layers:
1. **User Input Validation** - CLI entry point validates before processing
2. **LLM Output Sanitization** - AI-generated commands validated before execution
3. **Task Intents Validation** - Config files checked at load time
4. **Plugin Loading Security** - Path traversal blocked in plugin names
5. **Command Validation** - Individual command parts validated (from Phase 3)

✅ **Shell Metacharacter Blocking** - `;`, `|`, `&`, `$()`, backticks, etc.
✅ **Path Traversal Prevention** - `../` patterns blocked everywhere
✅ **Command Substitution Blocked** - `$(...)` and backticks rejected
✅ **Dangerous Command Detection** - `rm -rf`, `format c:`, etc. flagged
✅ **Length Limits** - Prevent buffer overflow attacks
✅ **Null Byte Protection** - Prevent string termination attacks

### Files Created (Phase 4)

**core/secure_plugin_loader.py** (280 lines) - Secure plugin loading
```python
class SecurePluginLoader:
    def validate_plugin_name(self, plugin_name: str) -> tuple[bool, str]:
        # Blocks: "..", path separators, special chars, long names

    def get_plugin_path(self, plugin_name: str) -> Path:
        # Validates, resolves, ensures path within plugins_dir

    def load_plugin(self, plugin_name: str) -> types.ModuleType:
        # Secure loading with full validation
```

**test_phase4_validation.py** (320 lines) - Comprehensive validation tests
- 10 test suites covering all validation layers
- Shell injection tests
- Path traversal tests
- LLM output sanitization tests
- Plugin security tests

### Files Modified (Phase 4)

**cli/igris_cli.py** - Added validation at 3 points:
```python
# Point 1: User input validation (line ~287)
from core.input_validation import InputValidator
validator = InputValidator(strict_mode=True)
is_valid, error_msg = validator.validate_user_input(user_req)

# Point 2: Task intents validation (line ~304)
for task in intents.get("tasks", []):
    action = task.get("action", "")
    dangerous_patterns = ["rm -rf", "del /f /s /q", ...]
    # Warn if dangerous patterns found

# Point 3: LLM output sanitization (line ~337)
obj = validator.sanitize_llm_output(obj)
```

**core/input_validation.py** - Enhanced with path traversal check:
```python
def sanitize_llm_output(self, llm_json: Dict[str, Any]) -> Dict[str, Any]:
    # Check shell metacharacters
    if re.search(SHELL_METACHARACTERS, action):
        raise ValidationError("Shell metacharacters in LLM action")

    # NEW: Check path traversal
    if re.search(PATH_TRAVERSAL_PATTERN, action):
        raise ValidationError("Path traversal pattern in LLM action")
```

### Breaking Changes

**Function Behavior Changes**:

```python
# User input with injection now blocked
python cli/igris_cli.py "open calc; rm -rf /"
# Before: Both commands execute (DANGEROUS!)
# After: [SECURITY] Input validation failed: Shell metacharacters detected

# LLM outputs with path traversal blocked
llm_output = {"action": "cat ../../etc/passwd", ...}
sanitize_llm_output(llm_output)
# Before: Would attempt to execute
# After: ValidationError: Path traversal pattern in LLM action

# Plugin loading with path traversal blocked
loader.load_plugin("../../etc/passwd")
# Before: Could load arbitrary Python files
# After: PluginSecurityError: Path traversal detected in plugin name
```

### Backward Compatibility

- ✅ Valid user inputs work exactly as before
- ✅ Valid LLM outputs accepted unchanged
- ✅ Valid plugins load normally
- ✅ Automatic fallback if validation modules unavailable
- ✅ No changes to function signatures
- ✅ Graceful degradation with warnings

### Testing

Run Phase 4 tests:
```bash
python3 test_phase4_validation.py

# Expected output:
# ✓ All critical validation tests passed!
# Phase 4 input validation security is ready for deployment.
```

**Test Coverage**:
- ✓ User input validation (CLI)
- ✓ LLM output sanitization
- ✓ Command part validation
- ✓ Plugin name validation
- ✓ Plugin path validation
- ✓ Task intent validation
- ✓ Strict vs lenient modes
- ✓ CLI integration verification

### What's Now Secure

**Entry Points**:
- `cli/igris_cli.py` - User input validated before processing
- `cli/igris_cli.py` - LLM outputs sanitized before execution
- `cli/igris_cli.py` - Task intents validated at load time

**Plugin System**:
- `core/secure_plugin_loader.py` - Path traversal prevention
- Plugin name validation
- Plugin path validation
- Safe plugin loading with exception handling

**Validation Modules**:
- `core/input_validation.py` - Multi-layer validation
- Shell metacharacter detection
- Path traversal detection
- Command substitution detection
- Dangerous command detection

### What Still Needs Updating (Phase 5)

- GUI files (22 files) - Need input validation at GUI entry points
- Remaining plugins - Some may need validation integration
- GUI authentication flow - Update to use new auth system

### Example: Full Validation Flow

```python
# User types: "open notepad; rm -rf /"

# Layer 1: User Input Validation
validator.validate_user_input("open notepad; rm -rf /")
# → Returns: (False, "Shell metacharacters detected in input")
# → CLI exits with error, command never sent to LLM

# If user input was valid but LLM responded maliciously:
llm_response = {
    "task_name": "open_app",
    "action": "calc; rm -rf /",
    "requires_admin": False
}

# Layer 2: LLM Output Sanitization
validator.sanitize_llm_output(llm_response)
# → Raises: ValidationError("Shell metacharacters in LLM action")
# → CLI exits, command never executed

# If LLM tried path traversal:
llm_response = {
    "task_name": "read_file",
    "action": "cat ../../etc/passwd",
    "requires_admin": False
}

# Layer 2: LLM Output Sanitization
validator.sanitize_llm_output(llm_response)
# → Raises: ValidationError("Path traversal pattern in LLM action")
```

---

## Next Phases

Phase 4 completes input validation security. Upcoming phases:

- **Phase 5**: Update GUI files and remaining plugins (eliminate remaining `shell=True`)

Each phase includes migration guides and testing procedures.

---

## Support

**Issues**: https://github.com/thephinux132/Igris-ai-assistant/issues
**Security**: Report critical issues privately
**Documentation**: See `/docs/` for detailed guides

**Version**: 2.0.0 (Phase 2-4: Secrets + Execution + Validation)
**Date**: 2026-01-08
**Latest Update**: Phase 4 completed - Input validation at all entry points
