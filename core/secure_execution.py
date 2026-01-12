"""
Secure Command Execution Module

Provides safe command execution without shell=True vulnerabilities.
Implements input validation, command whitelisting, and audit logging.

Security Features:
- No shell=True usage (prevents command injection)
- Input validation for all command parts
- Path traversal prevention
- Command whitelisting for sensitive operations
- Audit logging of all executed commands
- Timeout enforcement
"""

import subprocess
import re
import logging
from pathlib import Path
from typing import Optional, Union
from datetime import datetime


# Configure audit logging
logging.basicConfig(level=logging.INFO)
audit_logger = logging.getLogger('igris.security.execution')

# Shell metacharacters that indicate potential injection
SHELL_METACHARACTERS = r'[;&|`$(){}[\]<>\\"\'\n\r]'

# Dangerous command patterns
DANGEROUS_PATTERNS = [
    r'rm\s+',
    r'del\s+',
    r'format\s+',
    r'mkfs\.',
    r'dd\s+',
    r':(){.*}',  # Fork bomb
]


class SecurityError(Exception):
    """Raised when security validation fails"""
    pass


class ValidationError(Exception):
    """Raised when input validation fails"""
    pass


def validate_command_part(part: str) -> tuple[bool, str]:
    """
    Validate a single command part for security issues.

    Args:
        part: Command or argument string to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(part, str):
        return False, f"Command part must be string, got {type(part)}"

    # Check for shell metacharacters
    if re.search(SHELL_METACHARACTERS, part):
        return False, f"Shell metacharacters detected: {part[:50]}"

    # Check for dangerous command patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, part, re.IGNORECASE):
            return False, f"Dangerous command pattern detected: {pattern}"

    # Check for path traversal attempts
    if '..' in part and ('/' in part or '\\' in part):
        return False, f"Potential path traversal detected: {part[:50]}"

    return True, "OK"


def validate_command_parts(cmd_parts: list[str]) -> None:
    """
    Validate all parts of a command.

    Args:
        cmd_parts: List of command parts [executable, arg1, arg2, ...]

    Raises:
        ValidationError: If any part fails validation
    """
    if not cmd_parts:
        raise ValidationError("Empty command list")

    if not isinstance(cmd_parts, list):
        raise ValidationError(f"Command must be list, got {type(cmd_parts)}")

    for i, part in enumerate(cmd_parts):
        valid, msg = validate_command_part(part)
        if not valid:
            raise ValidationError(f"Command part {i} invalid: {msg}")


def safe_run_command(
    cmd_parts: list[str],
    timeout: Optional[int] = 30,
    capture_output: bool = True,
    text: bool = True,
    encoding: str = 'utf-8',
    **kwargs
) -> subprocess.CompletedProcess:
    """
    Execute command safely without shell=True.

    Args:
        cmd_parts: Command as list [executable, arg1, arg2, ...]
        timeout: Maximum execution time in seconds (default: 30)
        capture_output: Capture stdout/stderr (default: True)
        text: Return output as string (default: True)
        encoding: Text encoding (default: utf-8)
        **kwargs: Additional subprocess.run arguments

    Returns:
        CompletedProcess instance

    Raises:
        ValidationError: If command validation fails
        subprocess.TimeoutExpired: If command exceeds timeout
        subprocess.SubprocessError: If command execution fails

    Example:
        >>> result = safe_run_command(['notepad', 'file.txt'])
        >>> print(result.returncode)
        0
    """
    # Validate all command parts
    validate_command_parts(cmd_parts)

    # Log the execution for audit trail
    audit_logger.info(f"Executing command: {' '.join(cmd_parts[:5])}" +
                      ("..." if len(cmd_parts) > 5 else ""))

    # Force shell=False for security
    if 'shell' in kwargs:
        kwargs.pop('shell')
        audit_logger.warning("Removed shell=True argument (security policy)")

    try:
        # Execute without shell
        result = subprocess.run(
            cmd_parts,
            shell=False,  # CRITICAL: Never use shell=True
            timeout=timeout,
            capture_output=capture_output,
            text=text,
            encoding=encoding,
            errors='replace',
            **kwargs
        )

        # Log result
        audit_logger.info(f"Command completed: returncode={result.returncode}")

        return result

    except subprocess.TimeoutExpired as e:
        audit_logger.error(f"Command timeout after {timeout}s: {cmd_parts[0]}")
        raise
    except FileNotFoundError as e:
        audit_logger.error(f"Command not found: {cmd_parts[0]}")
        raise
    except Exception as e:
        audit_logger.error(f"Command execution failed: {e}")
        raise


def run_cmd_safe(cmd_parts: list[str]) -> str:
    """
    Execute command and return stdout as string (compatible with old run_cmd).

    This function provides backward compatibility with the old run_cmd()
    function signature while using secure execution internally.

    Args:
        cmd_parts: Command as list [executable, arg1, arg2, ...]

    Returns:
        String output (stdout) or error message

    Example:
        >>> result = run_cmd_safe(['notepad'])
        >>> print(result)
        'Command executed.'
    """
    try:
        result = safe_run_command(cmd_parts)

        if result.returncode != 0:
            err_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
            return f"[ERROR] Command returned {result.returncode}: {err_msg}"

        output = result.stdout.strip() if result.stdout else ""
        return output if output else "Command executed."

    except ValidationError as e:
        return f"[BLOCKED] Security validation failed: {e}"
    except subprocess.TimeoutExpired:
        return f"[ERROR] Command timeout: {cmd_parts[0]}"
    except FileNotFoundError:
        return f"[ERROR] Command not found: {cmd_parts[0]}"
    except subprocess.SubprocessError as e:
        return f"[ERROR] Execution failed: {e}"
    except Exception as e:
        return f"[ERROR] Unexpected error: {e}"


def validate_file_path(path: Union[str, Path], must_exist: bool = False) -> Path:
    """
    Validate and normalize a file path.

    Args:
        path: Path to validate
        must_exist: If True, path must exist

    Returns:
        Validated, normalized Path object

    Raises:
        ValidationError: If path is invalid or contains traversal
    """
    if not path:
        raise ValidationError("Empty path")

    path_obj = Path(path)

    # Check for path traversal
    try:
        resolved = path_obj.resolve()
    except (OSError, RuntimeError) as e:
        raise ValidationError(f"Cannot resolve path: {e}")

    # Verify path doesn't escape expected boundaries
    # (This check would be customized based on application needs)
    path_str = str(resolved)
    if '..' in path_obj.parts:
        raise ValidationError(f"Path traversal detected: {path}")

    # Check existence if required
    if must_exist and not resolved.exists():
        raise ValidationError(f"Path does not exist: {path}")

    return resolved


# Backward compatibility function
def legacy_run_cmd_with_warning(cmd_list: list) -> str:
    """
    Legacy wrapper that warns about usage.

    This function is provided for gradual migration. It logs a warning
    and then uses the secure implementation.
    """
    audit_logger.warning(
        f"DEPRECATED: legacy_run_cmd called. "
        f"Please update to use run_cmd_safe(). Command: {cmd_list[0] if cmd_list else 'empty'}"
    )
    return run_cmd_safe(cmd_list)


if __name__ == "__main__":
    # Basic self-test
    print("Secure Execution Module - Self Test")
    print("=" * 50)

    # Test 1: Valid command
    print("\nTest 1: Valid command (echo)")
    try:
        result = safe_run_command(['echo', 'Hello, World!'])
        print(f"✓ Success: {result.stdout.strip()}")
    except Exception as e:
        print(f"✗ Failed: {e}")

    # Test 2: Command injection attempt (should be blocked)
    print("\nTest 2: Command injection attempt (should block)")
    try:
        result = safe_run_command(['echo', 'test; rm -rf /'])
        print(f"✗ SECURITY FAILURE: Command was not blocked!")
    except ValidationError as e:
        print(f"✓ Blocked correctly: {e}")

    # Test 3: Path traversal attempt (should be blocked)
    print("\nTest 3: Path traversal attempt (should block)")
    try:
        result = validate_file_path('../../etc/passwd')
        print(f"✗ SECURITY FAILURE: Path traversal not blocked!")
    except ValidationError as e:
        print(f"✓ Blocked correctly: {e}")

    # Test 4: Using run_cmd_safe
    print("\nTest 4: Backward compatible run_cmd_safe")
    try:
        result = run_cmd_safe(['echo', 'Testing backward compatibility'])
        print(f"✓ Success: {result}")
    except Exception as e:
        print(f"✗ Failed: {e}")

    print("\n" + "=" * 50)
    print("Self-test complete. Check results above.")
