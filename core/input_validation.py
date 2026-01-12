"""
Input Validation Module

Provides multi-layer validation for all user inputs:
- User input from CLI/GUI
- LLM outputs from Ollama
- task_intents.json configuration
- Plugin paths and names

Defense in depth: Validate at every layer to prevent injection attacks.
"""

import re
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
validator_logger = logging.getLogger('igris.security.validation')

# Security patterns
SHELL_METACHARACTERS = r'[;&|`$(){}[\]<>\\"\n\r]'
PATH_TRAVERSAL_PATTERN = r'\.\.[/\\]'
DANGEROUS_COMMANDS = [
    'rm', 'del', 'format', 'mkfs', 'dd', ':(){', 'fork',
    'rundll32', 'regsvr32', 'mshta', 'wscript', 'cscript'
]

# Maximum input lengths
MAX_USER_INPUT_LENGTH = 1000
MAX_COMMAND_LENGTH = 500
MAX_PLUGIN_NAME_LENGTH = 100


class ValidationError(Exception):
    """Raised when validation fails"""
    pass


class InputValidator:
    """
    Multi-layer input validation.

    Provides validation for all untrusted input sources.
    """

    def __init__(self, strict_mode: bool = True):
        """
        Initialize validator.

        Args:
            strict_mode: If True, applies strictest validation rules
        """
        self.strict_mode = strict_mode
        validator_logger.info(f"InputValidator initialized (strict_mode={strict_mode})")

    def validate_user_input(self, user_text: str) -> Tuple[bool, str]:
        """
        Validate text input from user (CLI or GUI).

        Args:
            user_text: Raw user input text

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(user_text, str):
            return False, f"Input must be string, got {type(user_text)}"

        # Check length
        if len(user_text) > MAX_USER_INPUT_LENGTH:
            return False, f"Input too long: {len(user_text)} chars (max: {MAX_USER_INPUT_LENGTH})"

        # Check for null bytes (can bypass filters)
        if '\x00' in user_text:
            return False, "Null bytes not allowed in input"

        # Check for shell metacharacters (if strict)
        if self.strict_mode:
            if re.search(SHELL_METACHARACTERS, user_text):
                return False, f"Shell metacharacters detected in input"

        # Check for path traversal
        if re.search(PATH_TRAVERSAL_PATTERN, user_text):
            return False, "Path traversal pattern detected"

        # Check for dangerous command patterns
        lower_text = user_text.lower()
        for cmd in DANGEROUS_COMMANDS:
            if cmd in lower_text:
                # Additional context check
                if re.search(r'\b' + re.escape(cmd) + r'\b', lower_text):
                    return False, f"Potentially dangerous command detected: {cmd}"

        return True, "OK"

    def sanitize_llm_output(self, llm_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize and validate LLM output JSON.

        Args:
            llm_json: Parsed JSON from LLM

        Returns:
            Sanitized JSON

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(llm_json, dict):
            raise ValidationError(f"LLM output must be dict, got {type(llm_json)}")

        # Required keys
        required_keys = ['task_name', 'action', 'requires_admin']
        for key in required_keys:
            if key not in llm_json:
                raise ValidationError(f"LLM output missing required key: {key}")

        # Validate action string
        action = llm_json.get('action', '')
        if not isinstance(action, str):
            raise ValidationError(f"Action must be string, got {type(action)}")

        if len(action) > MAX_COMMAND_LENGTH:
            raise ValidationError(f"Action too long: {len(action)} chars")

        # Check for shell injection in action
        if re.search(SHELL_METACHARACTERS, action):
            validator_logger.warning(f"Shell metacharacters in LLM action: {action[:50]}")
            # In strict mode, block it
            if self.strict_mode:
                raise ValidationError("Shell metacharacters in LLM action")

        # Check for path traversal in action
        if re.search(PATH_TRAVERSAL_PATTERN, action):
            validator_logger.warning(f"Path traversal pattern in LLM action: {action[:50]}")
            if self.strict_mode:
                raise ValidationError("Path traversal pattern in LLM action")

        # Validate requires_admin is boolean
        requires_admin = llm_json.get('requires_admin')
        if not isinstance(requires_admin, bool):
            # Try to convert
            if requires_admin in ['true', 'True', '1', 1]:
                llm_json['requires_admin'] = True
            elif requires_admin in ['false', 'False', '0', 0, None]:
                llm_json['requires_admin'] = False
            else:
                raise ValidationError(f"Invalid requires_admin value: {requires_admin}")

        validator_logger.info(f"Validated LLM output: {llm_json.get('task_name')}")
        return llm_json

    def validate_plugin_name(self, plugin_name: str) -> Tuple[bool, str, str]:
        """
        Validate plugin name for security issues.

        Args:
            plugin_name: Plugin name (may include "plugin:" prefix)

        Returns:
            Tuple of (is_valid, sanitized_name, error_message)
        """
        if not isinstance(plugin_name, str):
            return False, "", f"Plugin name must be string, got {type(plugin_name)}"

        # Remove "plugin:" prefix if present
        if plugin_name.startswith("plugin:"):
            plugin_name = plugin_name[7:]  # len("plugin:") = 7

        # Check length
        if len(plugin_name) > MAX_PLUGIN_NAME_LENGTH:
            return False, "", f"Plugin name too long: {len(plugin_name)}"

        # Check for path traversal
        if '..' in plugin_name:
            return False, "", "Path traversal detected in plugin name"

        # Check for path separators
        if '/' in plugin_name or '\\' in plugin_name:
            return False, "", "Path separators not allowed in plugin name"

        # Check for special characters
        if not re.match(r'^[a-zA-Z0-9_-]+$', plugin_name):
            return False, "", "Plugin name contains invalid characters"

        return True, plugin_name, "OK"

    def validate_plugin_path(self, plugin_name: str, plugins_dir: Path) -> Path:
        """
        Validate and resolve plugin path securely.

        Args:
            plugin_name: Plugin name
            plugins_dir: Base plugins directory

        Returns:
            Resolved, validated Path object

        Raises:
            ValidationError: If validation fails
        """
        # Validate name first
        is_valid, sanitized_name, error = self.validate_plugin_name(plugin_name)
        if not is_valid:
            raise ValidationError(f"Invalid plugin name: {error}")

        # Construct path
        plugin_path = plugins_dir / f"{sanitized_name}.py"

        # Resolve to absolute path
        try:
            resolved_path = plugin_path.resolve()
        except (OSError, RuntimeError) as e:
            raise ValidationError(f"Cannot resolve plugin path: {e}")

        # Ensure path is within plugins directory
        try:
            resolved_path.relative_to(plugins_dir.resolve())
        except ValueError:
            raise ValidationError(
                f"Plugin path outside allowed directory: {resolved_path}"
            )

        # Check file exists
        if not resolved_path.exists():
            raise ValidationError(f"Plugin file not found: {sanitized_name}")

        # Check it's a file (not directory)
        if not resolved_path.is_file():
            raise ValidationError(f"Plugin path is not a file: {sanitized_name}")

        validator_logger.info(f"Validated plugin path: {resolved_path}")
        return resolved_path

    def validate_task_intents_file(self, intents_path: Path) -> List[Dict]:
        """
        Validate task_intents.json file at load time.

        Args:
            intents_path: Path to task_intents.json

        Returns:
            List of validated task dictionaries

        Raises:
            ValidationError: If validation fails
        """
        # Check file exists
        if not intents_path.exists():
            raise ValidationError(f"Task intents file not found: {intents_path}")

        # Load JSON
        try:
            content = intents_path.read_text(encoding='utf-8')
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON in task intents: {e}")
        except Exception as e:
            raise ValidationError(f"Cannot read task intents file: {e}")

        # Validate structure
        if not isinstance(data, dict):
            raise ValidationError("Task intents root must be a dict")

        if 'tasks' not in data:
            raise ValidationError("Task intents missing 'tasks' key")

        tasks = data['tasks']
        if not isinstance(tasks, list):
            raise ValidationError("'tasks' must be a list")

        # Validate each task
        validated_tasks = []
        for i, task in enumerate(tasks):
            try:
                validated_task = self._validate_task_intent(task, i)
                validated_tasks.append(validated_task)
            except ValidationError as e:
                validator_logger.error(f"Task {i} validation failed: {e}")
                if self.strict_mode:
                    raise
                # In non-strict mode, skip invalid tasks
                continue

        validator_logger.info(
            f"Validated {len(validated_tasks)} tasks from {intents_path}"
        )
        return validated_tasks

    def _validate_task_intent(self, task: Dict, index: int) -> Dict:
        """
        Validate a single task intent entry.

        Args:
            task: Task dictionary
            index: Task index (for error messages)

        Returns:
            Validated task dictionary

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(task, dict):
            raise ValidationError(f"Task {index} must be dict, got {type(task)}")

        # Check required fields
        required_fields = ['task', 'action']
        for field in required_fields:
            if field not in task:
                # Check alternative names
                if field == 'task' and 'task_name' in task:
                    task['task'] = task['task_name']
                else:
                    raise ValidationError(f"Task {index} missing field: {field}")

        # Validate action
        action = task['action']
        if not isinstance(action, str):
            raise ValidationError(f"Task {index} action must be string")

        if len(action) > MAX_COMMAND_LENGTH:
            raise ValidationError(
                f"Task {index} action too long: {len(action)} chars"
            )

        # Check action type
        if action.startswith("plugin:"):
            # Validate plugin name
            is_valid, sanitized, error = self.validate_plugin_name(action)
            if not is_valid:
                raise ValidationError(f"Task {index} invalid plugin: {error}")

        elif action.startswith("python "):
            # Python script execution - validate path
            script_path = action[7:]  # len("python ") = 7
            if '..' in script_path:
                raise ValidationError(f"Task {index} python script has path traversal")

        else:
            # Regular command - check for dangerous patterns
            if self.strict_mode:
                if re.search(SHELL_METACHARACTERS, action):
                    validator_logger.warning(
                        f"Task {index} has shell metacharacters: {action[:50]}"
                    )

        # Ensure requires_admin field exists (default False)
        if 'requires_admin' not in task:
            task['requires_admin'] = False

        return task

    def validate_file_path(self, path: str, allowed_dirs: Optional[List[Path]] = None) -> Path:
        """
        Validate a file path for security issues.

        Args:
            path: File path to validate
            allowed_dirs: List of allowed base directories (None = any)

        Returns:
            Validated, resolved Path object

        Raises:
            ValidationError: If validation fails
        """
        if not path:
            raise ValidationError("Empty file path")

        # Convert to Path object
        path_obj = Path(path)

        # Check for path traversal
        if '..' in path_obj.parts:
            raise ValidationError(f"Path traversal detected: {path}")

        # Resolve to absolute path
        try:
            resolved = path_obj.resolve()
        except (OSError, RuntimeError) as e:
            raise ValidationError(f"Cannot resolve path: {e}")

        # Check against allowed directories if specified
        if allowed_dirs:
            is_allowed = False
            for allowed_dir in allowed_dirs:
                try:
                    resolved.relative_to(allowed_dir.resolve())
                    is_allowed = True
                    break
                except ValueError:
                    continue

            if not is_allowed:
                raise ValidationError(
                    f"Path outside allowed directories: {resolved}"
                )

        return resolved


class LLMOutputSanitizer:
    """
    Specialized sanitizer for LLM outputs.

    Provides additional sanitization beyond basic validation.
    """

    def __init__(self):
        self.validator = InputValidator(strict_mode=True)

    def sanitize_json(self, llm_response: str) -> Dict[str, Any]:
        """
        Parse and sanitize LLM JSON response.

        Args:
            llm_response: Raw LLM response string

        Returns:
            Sanitized JSON dictionary

        Raises:
            ValidationError: If parsing or validation fails
        """
        # Extract JSON from response (LLM might include extra text)
        json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if not json_match:
            raise ValidationError("No JSON found in LLM response")

        json_str = json_match.group(0)

        # Parse JSON
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON from LLM: {e}")

        # Validate and sanitize
        return self.validator.sanitize_llm_output(parsed)


if __name__ == "__main__":
    # Self-test
    print("Input Validation Module - Self Test")
    print("=" * 60)

    validator = InputValidator(strict_mode=True)

    # Test 1: Valid user input
    print("\n[Test 1] Valid user input")
    is_valid, msg = validator.validate_user_input("open notepad")
    print(f"{'✓' if is_valid else '✗'} Result: {msg}")

    # Test 2: Shell injection attempt
    print("\n[Test 2] Shell injection attempt")
    is_valid, msg = validator.validate_user_input("test; rm -rf /")
    print(f"{'✓' if not is_valid else '✗'} Blocked: {msg}")

    # Test 3: Path traversal attempt
    print("\n[Test 3] Path traversal attempt")
    is_valid, msg = validator.validate_user_input("../../etc/passwd")
    print(f"{'✓' if not is_valid else '✗'} Blocked: {msg}")

    # Test 4: Valid plugin name
    print("\n[Test 4] Valid plugin name")
    is_valid, sanitized, msg = validator.validate_plugin_name("plugin:network_scanner")
    print(f"{'✓' if is_valid else '✗'} Sanitized: {sanitized}")

    # Test 5: Invalid plugin name (path traversal)
    print("\n[Test 5] Invalid plugin name (path traversal)")
    is_valid, sanitized, msg = validator.validate_plugin_name("plugin:../../malware")
    print(f"{'✓' if not is_valid else '✗'} Blocked: {msg}")

    # Test 6: LLM output sanitization
    print("\n[Test 6] LLM output sanitization")
    try:
        llm_output = {
            'task_name': 'open calculator',
            'action': 'calc',
            'requires_admin': False
        }
        sanitized = validator.sanitize_llm_output(llm_output)
        print(f"✓ Sanitized LLM output: {sanitized['task_name']}")
    except ValidationError as e:
        print(f"✗ Failed: {e}")

    # Test 7: Dangerous LLM output (should be blocked in strict mode)
    print("\n[Test 7] Dangerous LLM output")
    try:
        llm_output = {
            'task_name': 'malicious',
            'action': 'calc; rm -rf /',
            'requires_admin': False
        }
        sanitized = validator.sanitize_llm_output(llm_output)
        print(f"✗ Should have been blocked!")
    except ValidationError as e:
        print(f"✓ Blocked correctly: {e}")

    print("\n" + "=" * 60)
    print("Self-test complete.")
