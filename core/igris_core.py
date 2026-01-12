import json
import subprocess
import re
import hashlib
import getpass
from pathlib import Path
import psutil
import logging

# Import new security modules
try:
    from core.secrets_manager import SecretsManager
    from core.secure_auth import AuthenticationManager, RateLimitError, AuthenticationError
    from core.migration_utils import check_and_migrate
    SECURITY_MODULES_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Security modules not available: {e}")
    SECURITY_MODULES_AVAILABLE = False

def match_intent(user_input: str, intents: dict) -> dict | None:
    """
    Normalize both the user's text and each intent key by stripping out
    all non-alphanumeric characters, then match via substring lookup.
    """
    # Strip everything except letters+digits, lowercase
    clean_in = re.sub(r"\W+", "", user_input).lower()

    for intent in intents.get("tasks", []):
        key = intent.get("task") or intent.get("task_name")
        if not key:
            continue

        clean_key = re.sub(r"\W+", "", key).lower()
        if clean_key in clean_in:
            return intent

    return None


# Default Ollama model if not overridden
default_ollama_model = "hf.co/bartowski/Llama-3.2-1B-Instruct-GGUF:Q5_K_M"


def load_policy(policy_path: Path = None) -> dict:
    """
    Load the policy JSON from the given path or a default location.

    NOTE: In the new security model, the admin_pin_hash is stored in
    secure storage (Windows Credential Manager / keyring), not in the
    policy file. This function maintains backward compatibility.
    """
    if policy_path is None:
        policy_path = Path(__file__).parent / 'ai_script_policy.json'

    try:
        policy = json.loads(policy_path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        policy = {}

    # If using new security modules, load PIN hash from secure storage
    if SECURITY_MODULES_AVAILABLE:
        try:
            secrets_mgr = SecretsManager()
            pin_hash = secrets_mgr.get_pin_hash()

            # Only add to policy if PIN hash exists in secure storage
            if pin_hash:
                policy['admin_pin_hash'] = pin_hash
            # If no secure PIN but policy has old hash, migration needed
            elif 'admin_pin_hash' in policy:
                logging.info("Legacy PIN hash detected - migration recommended")
        except Exception as e:
            logging.error(f"Error loading PIN from secure storage: {e}")

    return policy


def run_cmd(cmd_list: list) -> str:
    """
    Execute a command list securely without shell=True.

    UPDATED: Now uses secure_execution module to prevent command injection.
    Falls back to legacy (unsafe) execution if security modules unavailable.

    Args:
        cmd_list: Command as list [executable, arg1, arg2, ...]

    Returns:
        Command output or error message

    Security:
        - No shell=True (prevents command injection)
        - Input validation on all command parts
        - Command whitelisting for sensitive operations
        - Audit logging of all executions
    """
    # Use new secure execution if available
    if SECURITY_MODULES_AVAILABLE:
        try:
            from core.secure_execution import run_cmd_safe
            from core.input_validation import ValidationError

            # Use secure execution
            result = run_cmd_safe(cmd_list)
            return result

        except ValidationError as e:
            # Command was blocked by security validation
            logging.warning(f"Command blocked by security: {e}")
            return f"[BLOCKED] Security validation failed: {e}"
        except ImportError as e:
            logging.error(f"Failed to import secure_execution: {e}")
            # Fall through to legacy execution
            pass
        except Exception as e:
            logging.error(f"Secure execution failed: {e}")
            return f"[ERROR] Execution failed: {e}"

    # Fallback to legacy execution (UNSAFE - for backward compatibility only)
    logging.warning("Using legacy command execution - security upgrade recommended")

    command_str = " ".join(cmd_list)
    try:
        proc = subprocess.run(
            command_str,
            capture_output=True,
            text=True,
            shell=True,  # UNSAFE: Only used if secure modules unavailable
            check=False,
            encoding='utf-8',
            errors='replace'
        )
    except FileNotFoundError:
        return f"[ERROR] Command not found: '{cmd_list[0] if cmd_list else 'unknown'}'"
    except subprocess.CalledProcessError as e:
        if e.returncode == 1 and "Access is denied" in (e.stderr or e.stdout):
            return f"[ERROR] Permission denied: '{command_str}'. Ensure you have necessary privileges."
        return f"[ERROR] Command '{command_str}' failed (code {e.returncode}): {e.stderr or e.stdout}"
    except OSError as e:
        return f"[ERROR] OS error executing '{command_str}': {e}"
    except Exception as e:
        return f"[ERROR] Unexpected error executing '{command_str}': {e}"

    out = proc.stdout.strip() if proc.stdout else ""
    err = proc.stderr.strip() if proc.stderr else ""
    if proc.returncode != 0:
        return f"[ERROR] Command '{command_str}' returned {proc.returncode}: {err or out}"
    return out if out else "Command executed."


def ask_ollama(prompt: str, model: str = None) -> str:
    """
    Call Ollama with the given prompt and return its raw response.
    """
    if model is None:
        model = default_ollama_model
    intent_prompt = prompt
    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=intent_prompt,
            capture_output=True,
            text=True,
            timeout=60,
            encoding='utf-8'
        )
        if result.returncode != 0:
            return f"[FATAL] Ollama error: {result.stderr.strip()}"
        return result.stdout.strip()
    except Exception as e:
        return f"[FATAL] Exception: {e}"


def respond_with_review(user_input: str) -> str:
    """
    Handle basic system status queries locally, without LLM.
    """
    ui = user_input.lower()
    if "system" in ui and ("status" in ui or "stats" in ui):
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        return (
            f"CPU Load: {cpu}%\n"
            f"Memory Usage: {mem.percent}% ({mem.used // (1024 ** 2)} MB / {mem.total // (1024 ** 2)} MB)\n"
            f"Disk Usage (C:\\): {disk.percent}% ({disk.free // (1024 ** 3)} GB free / {disk.total // (1024 ** 3)} GB total)\n"
            f"Uptime: {psutil.boot_time()}"
        )
    if "cpu" in ui and "status" in ui:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        return f"CPU: {cpu}%, Memory: {mem.percent}%"
    if "uptime" in ui:
        return f"Uptime: {psutil.boot_time()}"
    if "disk" in ui:
        disk = psutil.disk_usage("C:\\")
        return f"Disk Usage: {disk.percent}%"
    return None


def cli_show_fingerprint_prompt() -> bool:
    """
    DEPRECATED: Fingerprint authentication was simulated.
    This function is kept for backward compatibility but always returns False.
    Use authenticate_admin() instead.
    """
    logging.warning("DEPRECATED: cli_show_fingerprint_prompt() called - simulated auth removed")
    print("[SECURITY] Simulated fingerprint authentication has been removed.")
    print("[SECURITY] Please use PIN authentication instead.")
    return False


def cli_prompt_for_pin(pin_hash: str = None) -> bool:
    """
    Prompt user for PIN and verify.

    UPDATED: Now uses Argon2id verification if new security modules available.
    Falls back to SHA256 for legacy compatibility.

    Args:
        pin_hash: PIN hash (optional, loads from secure storage if None)

    Returns:
        True if PIN verified successfully
    """
    # Use new secure authentication if available
    if SECURITY_MODULES_AVAILABLE:
        try:
            auth_mgr = AuthenticationManager()

            # Check if PIN is configured
            if not auth_mgr.is_pin_configured():
                print("[SECURITY] Admin PIN not configured.")
                print("[SECURITY] Run migration or setup first.")
                return False

            # Authenticate with PIN
            entered = getpass.getpass("🔑 Enter admin PIN: ")
            return auth_mgr.verify_pin(entered)

        except RateLimitError as e:
            print(f"[SECURITY] {e}")
            return False
        except AuthenticationError as e:
            print(f"[SECURITY] {e}")
            return False
        except Exception as e:
            logging.error(f"Authentication error: {e}")
            return False

    # Fallback to legacy SHA256 verification
    if pin_hash is None:
        policy = load_policy()
        pin_hash = policy.get('admin_pin_hash')

        if not pin_hash:
            logging.error("No PIN hash available")
            return False

    entered = getpass.getpass("🔑 Enter admin PIN: ")
    hashed = hashlib.sha256(entered.encode('utf-8')).hexdigest()
    return hashed == pin_hash


def cli_confirm_by_voice(expected_phrase: str = "yes allow this") -> bool:
    """
    DEPRECATED: Voice authentication was simulated.
    This function is kept for backward compatibility but always returns False.
    Use authenticate_admin() instead.
    """
    logging.warning("DEPRECATED: cli_confirm_by_voice() called - simulated auth removed")
    print("[SECURITY] Simulated voice authentication has been removed.")
    print("[SECURITY] Please use PIN authentication instead.")
    return False


def authenticate_admin() -> bool:
    """
    Authenticate admin user.

    UPDATED: Now uses secure authentication with rate limiting.
    Simulated fingerprint/voice authentication has been removed.

    Returns:
        True if authenticated successfully
    """
    # Use new secure authentication if available
    if SECURITY_MODULES_AVAILABLE:
        try:
            auth_mgr = AuthenticationManager()

            # Check if PIN is configured
            if not auth_mgr.is_pin_configured():
                print("[SECURITY] Admin PIN not configured.")
                print("[SECURITY] Run setup or migration first.")

                # Offer to run migration
                try:
                    response = input("Run migration check now? (y/n): ").strip().lower()
                    if response == 'y':
                        from core.migration_utils import check_and_migrate
                        if check_and_migrate():
                            # Retry authentication after migration
                            auth_mgr = AuthenticationManager()
                            return auth_mgr.authenticate_admin()
                except KeyboardInterrupt:
                    return False

                return False

            # Authenticate with secure PIN
            return auth_mgr.authenticate_admin()

        except RateLimitError as e:
            print(f"[SECURITY] {e}")
            return False
        except AuthenticationError as e:
            print(f"[SECURITY] {e}")
            return False
        except Exception as e:
            logging.error(f"Authentication error: {e}")
            return False

    # Fallback to legacy authentication (deprecated)
    logging.warning("Using legacy authentication - security upgrade recommended")

    # Load policy for PIN hash
    policy = load_policy()
    pin_hash = policy.get('admin_pin_hash')

    if not pin_hash:
        print("[ERROR] No admin PIN configured and security modules not available.")
        return False

    # Only try PIN authentication (fingerprint/voice were fake anyway)
    return cli_prompt_for_pin(pin_hash)
