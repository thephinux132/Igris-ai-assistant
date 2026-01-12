#!/usr/bin/env python3
"""
Command Approval Workflow
Implements approval gates for elevated/dangerous commands.
"""

import re
import logging
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

logger = logging.getLogger(__name__)

class ApprovalLevel(Enum):
    AUTO = "auto"
    LOW = "low"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ApprovalRule:
    pattern: str
    level: ApprovalLevel
    message: str
    compiled: re.Pattern = None

    def __post_init__(self):
        self.compiled = re.compile(self.pattern, re.IGNORECASE)

    def matches(self, command: str) -> bool:
        return bool(self.compiled.search(command))

@dataclass
class ApprovalResult:
    approved: bool
    level: ApprovalLevel
    message: str
    requires_auth: bool = False

class ApprovalWorkflow:
    """Manages command approval workflow."""

    def __init__(self, rules_path: Optional[Path] = None):
        self.rules_path = rules_path or Path(__file__).parent.parent / "config" / "approval_rules.yaml"
        self.rules: list[ApprovalRule] = []
        self.auto_approve: list[re.Pattern] = []
        self.levels = {}
        self._load_rules()

    def _load_rules(self):
        """Load approval rules from YAML config."""
        if not YAML_AVAILABLE:
            logger.warning("PyYAML not available - using default rules")
            self._load_default_rules()
            return

        if not self.rules_path.exists():
            logger.warning(f"Rules file not found: {self.rules_path}")
            self._load_default_rules()
            return

        try:
            config = yaml.safe_load(self.rules_path.read_text())

            # Load approval rules
            for rule in config.get("approval_required", []):
                self.rules.append(ApprovalRule(
                    pattern=rule["pattern"],
                    level=ApprovalLevel(rule["level"]),
                    message=rule["message"]
                ))

            # Load auto-approve patterns
            for pattern in config.get("auto_approve", []):
                self.auto_approve.append(re.compile(pattern, re.IGNORECASE))

            # Load level configs
            self.levels = config.get("levels", {})

            logger.info(f"Loaded {len(self.rules)} approval rules")
        except Exception as e:
            logger.error(f"Failed to load rules: {e}")
            self._load_default_rules()

    def _load_default_rules(self):
        """Load minimal default rules."""
        self.rules = [
            ApprovalRule(r"^shutdown", ApprovalLevel.CRITICAL, "System shutdown"),
            ApprovalRule(r"^reboot", ApprovalLevel.CRITICAL, "System restart"),
            ApprovalRule(r"rm\s+-rf", ApprovalLevel.CRITICAL, "Recursive deletion"),
            ApprovalRule(r"^reg\s+", ApprovalLevel.CRITICAL, "Registry access"),
        ]
        self.auto_approve = [
            re.compile(r"^echo\s", re.IGNORECASE),
            re.compile(r"^dir\s|^ls\s", re.IGNORECASE),
        ]

    def check_command(self, command: str) -> Tuple[ApprovalLevel, Optional[str]]:
        """
        Check if command requires approval.

        Returns:
            (ApprovalLevel, message or None)
        """
        command = command.strip()

        # Check auto-approve first
        for pattern in self.auto_approve:
            if pattern.search(command):
                return ApprovalLevel.AUTO, None

        # Check approval rules
        for rule in self.rules:
            if rule.matches(command):
                return rule.level, rule.message

        # Default: low approval (just log)
        return ApprovalLevel.LOW, None

    def request_approval(self, command: str, level: ApprovalLevel, message: str) -> ApprovalResult:
        """
        Request user approval for command.

        Args:
            command: The command requiring approval
            level: Approval level required
            message: Description of what command does

        Returns:
            ApprovalResult with approval status
        """
        level_config = self.levels.get(level.value, {})
        requires_auth = level_config.get("auth_required", False)
        needs_phrase = level_config.get("confirmation_phrase", False)

        print(f"\n{'='*50}")
        print(f"⚠️  APPROVAL REQUIRED ({level.value.upper()})")
        print(f"{'='*50}")
        print(f"Command: {command}")
        print(f"Action:  {message}")
        print(f"{'='*50}")

        if needs_phrase:
            print(f"\nType 'CONFIRM {level.value.upper()}' to approve:")
            try:
                response = input("> ").strip()
                if response != f"CONFIRM {level.value.upper()}":
                    return ApprovalResult(False, level, "Confirmation phrase mismatch")
            except EOFError:
                return ApprovalResult(False, level, "Input error")
        else:
            print("\nApprove? [y/N]: ", end="")
            try:
                response = input().strip().lower()
                if response not in ('y', 'yes'):
                    return ApprovalResult(False, level, "User declined")
            except EOFError:
                return ApprovalResult(False, level, "Input error")

        # If auth required, verify identity
        if requires_auth:
            try:
                from core.secure_auth import AuthenticationManager
                auth = AuthenticationManager()
                if not auth.authenticate_admin():
                    return ApprovalResult(False, level, "Authentication failed", True)
            except ImportError:
                logger.warning("Auth module unavailable - skipping auth check")

        logger.info(f"Command approved: {command[:50]}...")
        return ApprovalResult(True, level, "Approved", requires_auth)

    def approve_command(self, command: str) -> ApprovalResult:
        """
        Full approval workflow for a command.

        Args:
            command: Command to approve

        Returns:
            ApprovalResult
        """
        level, message = self.check_command(command)

        if level == ApprovalLevel.AUTO:
            return ApprovalResult(True, level, "Auto-approved")

        if level == ApprovalLevel.LOW:
            logger.debug(f"Low-risk command: {command[:50]}")
            return ApprovalResult(True, level, "Low-risk approved")

        return self.request_approval(command, level, message or "Command requires approval")


# Convenience functions
_workflow = None

def get_workflow() -> ApprovalWorkflow:
    global _workflow
    if _workflow is None:
        _workflow = ApprovalWorkflow()
    return _workflow

def requires_approval(command: str) -> bool:
    """Quick check if command needs approval."""
    level, _ = get_workflow().check_command(command)
    return level in (ApprovalLevel.HIGH, ApprovalLevel.CRITICAL)

def approve(command: str) -> bool:
    """Request approval for command, return True if approved."""
    result = get_workflow().approve_command(command)
    return result.approved


# Self-test
if __name__ == "__main__":
    print("Approval Workflow Test")
    print("=" * 40)

    workflow = ApprovalWorkflow()

    test_commands = [
        "echo hello",
        "dir /s",
        "shutdown /s /t 0",
        "rm -rf /tmp/test",
        r"reg add HKLM\SOFTWARE\Test",
        "ping 8.8.8.8",
        "schtasks /create /tn test",
    ]
    for cmd in test_commands:
        level, msg = workflow.check_command(cmd)
        print(f"{level.value:8} | {cmd[:40]:<40} | {msg or '-'}")
