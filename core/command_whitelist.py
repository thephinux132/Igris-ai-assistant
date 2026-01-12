"""
Command Whitelist Module

Defines allowed commands, their security requirements, and argument validation.
Used by secure_execution module to enforce command restrictions.

Security Model:
- Default-deny: Only explicitly whitelisted commands are allowed
- Admin-required flag for sensitive operations
- Argument validation for each command
- Special handling for shell built-ins and system commands
"""

import re
from typing import Optional, Callable, Dict, List, Any
from pathlib import Path


class CommandPolicy:
    """Policy definition for a whitelisted command"""

    def __init__(
        self,
        name: str,
        requires_admin: bool = False,
        allowed_flags: Optional[List[str]] = None,
        max_args: Optional[int] = None,
        arg_validator: Optional[Callable] = None,
        description: str = ""
    ):
        self.name = name
        self.requires_admin = requires_admin
        self.allowed_flags = allowed_flags or []
        self.max_args = max_args
        self.arg_validator = arg_validator
        self.description = description

    def validate_args(self, args: List[str]) -> tuple[bool, str]:
        """
        Validate command arguments against policy.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check argument count
        if self.max_args is not None and len(args) > self.max_args:
            return False, f"Too many arguments: {len(args)} (max: {self.max_args})"

        # Check for disallowed flags
        if self.allowed_flags:
            for arg in args:
                if arg.startswith('-') or arg.startswith('/'):
                    if arg not in self.allowed_flags:
                        return False, f"Disallowed flag: {arg}"

        # Run custom validator if provided
        if self.arg_validator:
            try:
                is_valid, msg = self.arg_validator(args)
                if not is_valid:
                    return False, msg
            except Exception as e:
                return False, f"Validator error: {e}"

        return True, "OK"


# Argument validators for specific commands

def validate_shutdown_args(args: List[str]) -> tuple[bool, str]:
    """Validate shutdown command arguments"""
    allowed_flags = ['/s', '/r', '/h', '/t', '/f', '/c']

    for arg in args:
        if arg.startswith('/'):
            flag = arg.split()[0]  # Get flag without value
            if flag not in allowed_flags:
                return False, f"Disallowed shutdown flag: {flag}"

        # Check for immediate shutdown (dangerous)
        if arg == '/t' and len(args) > args.index('/t') + 1:
            try:
                timeout = int(args[args.index('/t') + 1])
                if timeout < 30:
                    return False, "Shutdown timeout must be at least 30 seconds"
            except (ValueError, IndexError):
                return False, "Invalid timeout value"

    return True, "OK"


def validate_schtasks_args(args: List[str]) -> tuple[bool, str]:
    """Validate schtasks command arguments"""
    if not args:
        return False, "schtasks requires arguments"

    # First arg should be operation
    operations = ['/Create', '/Delete', '/Query', '/Change', '/Run', '/End']
    if args[0] not in operations:
        return False, f"Invalid schtasks operation: {args[0]}"

    # Block dangerous operations
    dangerous_ops = ['/Delete']
    if args[0] in dangerous_ops and '/TN' not in args:
        return False, f"{args[0]} requires /TN (task name)"

    return True, "OK"


def validate_reg_args(args: List[str]) -> tuple[bool, str]:
    """Validate registry command arguments"""
    if not args:
        return False, "reg command requires arguments"

    # Only allow query operations by default (add/delete require explicit permission)
    allowed_ops = ['query', 'QUERY']
    if args[0] not in allowed_ops:
        return False, f"Registry operation not allowed: {args[0]}"

    return True, "OK"


def validate_powershell_args(args: List[str]) -> tuple[bool, str]:
    """Validate PowerShell command arguments"""
    # Block encoded commands (often used maliciously)
    for arg in args:
        if arg.lower() in ['-encodedcommand', '-enc', '-ec']:
            return False, "Encoded PowerShell commands not allowed"

    # Block download/execution patterns
    dangerous_cmdlets = ['invoke-webrequest', 'invoke-expression', 'iwr', 'iex']
    full_cmd = ' '.join(args).lower()
    for cmdlet in dangerous_cmdlets:
        if cmdlet in full_cmd:
            return False, f"PowerShell cmdlet not allowed: {cmdlet}"

    return True, "OK"


# =========================================================================
# COMMAND WHITELIST
# =========================================================================

COMMAND_WHITELIST: Dict[str, CommandPolicy] = {
    # Safe user applications (no admin required)
    'notepad': CommandPolicy(
        name='notepad',
        requires_admin=False,
        max_args=1,
        description='Text editor'
    ),
    'notepad.exe': CommandPolicy(
        name='notepad.exe',
        requires_admin=False,
        max_args=1,
        description='Text editor'
    ),
    'calc': CommandPolicy(
        name='calc',
        requires_admin=False,
        max_args=0,
        description='Calculator'
    ),
    'calc.exe': CommandPolicy(
        name='calc.exe',
        requires_admin=False,
        max_args=0,
        description='Calculator'
    ),
    'mspaint': CommandPolicy(
        name='mspaint',
        requires_admin=False,
        max_args=1,
        description='Paint application'
    ),
    'explorer': CommandPolicy(
        name='explorer',
        requires_admin=False,
        description='File explorer'
    ),
    'explorer.exe': CommandPolicy(
        name='explorer.exe',
        requires_admin=False,
        description='File explorer'
    ),

    # Microsoft Office applications (no admin required)
    'winword': CommandPolicy(
        name='winword',
        requires_admin=False,
        description='Microsoft Word'
    ),
    'excel': CommandPolicy(
        name='excel',
        requires_admin=False,
        description='Microsoft Excel'
    ),
    'powerpnt': CommandPolicy(
        name='powerpnt',
        requires_admin=False,
        description='Microsoft PowerPoint'
    ),
    'outlook': CommandPolicy(
        name='outlook',
        requires_admin=False,
        description='Microsoft Outlook'
    ),

    # System utilities (require admin)
    'shutdown': CommandPolicy(
        name='shutdown',
        requires_admin=True,
        allowed_flags=['/s', '/r', '/h', '/t', '/f', '/c'],
        arg_validator=validate_shutdown_args,
        description='System shutdown/restart'
    ),
    'schtasks': CommandPolicy(
        name='schtasks',
        requires_admin=True,
        allowed_flags=['/Create', '/Delete', '/Query', '/Change', '/Run', '/End',
                      '/TN', '/TR', '/SC', '/ST', '/F', '/MO', '/D'],
        arg_validator=validate_schtasks_args,
        description='Task scheduler'
    ),
    'reg': CommandPolicy(
        name='reg',
        requires_admin=True,
        arg_validator=validate_reg_args,
        description='Registry editor (query only)'
    ),
    'regedit': CommandPolicy(
        name='regedit',
        requires_admin=True,
        max_args=1,
        description='Registry editor GUI'
    ),

    # Network utilities (may require admin)
    'ipconfig': CommandPolicy(
        name='ipconfig',
        requires_admin=False,
        allowed_flags=['/all', '/release', '/renew', '/flushdns', '/displaydns'],
        description='IP configuration'
    ),
    'ping': CommandPolicy(
        name='ping',
        requires_admin=False,
        allowed_flags=['-n', '-w', '-t', '-4', '-6'],
        description='Network ping utility'
    ),
    'nslookup': CommandPolicy(
        name='nslookup',
        requires_admin=False,
        description='DNS lookup utility'
    ),
    'tracert': CommandPolicy(
        name='tracert',
        requires_admin=False,
        allowed_flags=['-d', '-h', '-w'],
        description='Trace route utility'
    ),
    'netstat': CommandPolicy(
        name='netstat',
        requires_admin=False,
        allowed_flags=['-a', '-n', '-o', '-b', '-p'],
        description='Network statistics'
    ),
    'nmap': CommandPolicy(
        name='nmap',
        requires_admin=False,  # Basic scans don't need admin
        allowed_flags=['-sn', '-sS', '-sT', '-p', '-A', '-O', '-v'],
        description='Network scanning tool'
    ),

    # System monitoring (no admin required)
    'tasklist': CommandPolicy(
        name='tasklist',
        requires_admin=False,
        allowed_flags=['/FO', '/NH', '/V'],
        description='List running processes'
    ),
    'systeminfo': CommandPolicy(
        name='systeminfo',
        requires_admin=False,
        description='Display system information'
    ),

    # Process control (requires admin for kill)
    'taskkill': CommandPolicy(
        name='taskkill',
        requires_admin=True,
        allowed_flags=['/F', '/IM', '/PID', '/T'],
        description='Terminate processes'
    ),

    # Management consoles (require admin)
    'services.msc': CommandPolicy(
        name='services.msc',
        requires_admin=True,
        max_args=0,
        description='Services manager'
    ),
    'devmgmt.msc': CommandPolicy(
        name='devmgmt.msc',
        requires_admin=True,
        max_args=0,
        description='Device manager'
    ),
    'diskmgmt.msc': CommandPolicy(
        name='diskmgmt.msc',
        requires_admin=True,
        max_args=0,
        description='Disk management'
    ),
    'compmgmt.msc': CommandPolicy(
        name='compmgmt.msc',
        requires_admin=True,
        max_args=0,
        description='Computer management'
    ),
    'taskschd.msc': CommandPolicy(
        name='taskschd.msc',
        requires_admin=True,
        max_args=0,
        description='Task scheduler'
    ),
    'eventvwr.msc': CommandPolicy(
        name='eventvwr.msc',
        requires_admin=True,
        max_args=0,
        description='Event viewer'
    ),
    'gpedit.msc': CommandPolicy(
        name='gpedit.msc',
        requires_admin=True,
        max_args=0,
        description='Group policy editor'
    ),

    # PowerShell (requires admin, heavily restricted)
    'powershell': CommandPolicy(
        name='powershell',
        requires_admin=True,
        arg_validator=validate_powershell_args,
        description='PowerShell (restricted)'
    ),
    'powershell.exe': CommandPolicy(
        name='powershell.exe',
        requires_admin=True,
        arg_validator=validate_powershell_args,
        description='PowerShell (restricted)'
    ),

    # Network tools
    'ssh': CommandPolicy(
        name='ssh',
        requires_admin=False,
        allowed_flags=['-p', '-i', '-L', '-R', '-D', '-N', '-f'],
        description='SSH client'
    ),
    'autossh': CommandPolicy(
        name='autossh',
        requires_admin=False,
        allowed_flags=['-M', '-f', '-N', '-L', '-R', '-p'],
        description='Auto-reconnecting SSH'
    ),

    # Docker (may require admin depending on setup)
    'docker': CommandPolicy(
        name='docker',
        requires_admin=False,  # Depends on user group
        allowed_flags=['ps', 'run', 'stop', 'start', 'exec', 'logs', 'images',
                      '-d', '-it', '-p', '--rm', '--name'],
        description='Docker container manager'
    ),

    # Python execution (for plugins)
    'python': CommandPolicy(
        name='python',
        requires_admin=False,
        description='Python interpreter'
    ),
    'python3': CommandPolicy(
        name='python3',
        requires_admin=False,
        description='Python 3 interpreter'
    ),
    'python.exe': CommandPolicy(
        name='python.exe',
        requires_admin=False,
        description='Python interpreter'
    ),

    # System commands via cmd
    'cmd': CommandPolicy(
        name='cmd',
        requires_admin=False,
        allowed_flags=['/c', '/k'],
        max_args=3,  # cmd /c <command>
        description='Command prompt'
    ),

    # Ollama (AI model)
    'ollama': CommandPolicy(
        name='ollama',
        requires_admin=False,
        allowed_flags=['run', 'pull', 'list'],
        description='Ollama LLM runtime'
    ),
}


def is_command_allowed(command: str) -> bool:
    """Alias for is_command_whitelisted for test compatibility"""
    return is_command_whitelisted(command)


def is_command_whitelisted(command: str) -> bool:
    """Check if a command is in the whitelist"""
    cmd_lower = command.lower()
    cmd_base = Path(command).name.lower()  # Handle full paths

    return cmd_lower in COMMAND_WHITELIST or cmd_base in COMMAND_WHITELIST


def get_command_policy(command: str) -> Optional[CommandPolicy]:
    """Get the policy for a whitelisted command"""
    cmd_lower = command.lower()
    cmd_base = Path(command).name.lower()

    if cmd_lower in COMMAND_WHITELIST:
        return COMMAND_WHITELIST[cmd_lower]
    elif cmd_base in COMMAND_WHITELIST:
        return COMMAND_WHITELIST[cmd_base]

    return None


def validate_command(cmd_parts: List[str]) -> tuple[bool, str, bool]:
    """
    Validate a command against the whitelist.

    Args:
        cmd_parts: Command parts [executable, arg1, arg2, ...]

    Returns:
        Tuple of (is_allowed, error_message, requires_admin)
    """
    if not cmd_parts:
        return False, "Empty command", False

    command = cmd_parts[0]
    args = cmd_parts[1:] if len(cmd_parts) > 1 else []

    # Get command policy
    policy = get_command_policy(command)

    if not policy:
        return False, f"Command not whitelisted: {command}", False

    # Validate arguments
    is_valid, msg = policy.validate_args(args)
    if not is_valid:
        return False, f"{command}: {msg}", policy.requires_admin

    return True, "OK", policy.requires_admin


if __name__ == "__main__":
    # Self-test
    print("Command Whitelist Module - Self Test")
    print("=" * 60)

    test_cases = [
        (['notepad', 'test.txt'], True, False),
        (['calc'], True, False),
        (['shutdown', '/r', '/t', '60'], True, True),
        (['shutdown', '/r', '/t', '5'], False, True),  # Too short timeout
        (['rm', '-rf', '/'], False, False),  # Not whitelisted
        (['powershell', '-enc', 'base64'], False, True),  # Encoded command blocked
        (['schtasks', '/Query'], True, True),
        (['ping', '-n', '4', 'google.com'], True, False),
        (['nmap', '-sn', '192.168.1.0/24'], True, False),
    ]

    for cmd_parts, should_pass, should_require_admin in test_cases:
        is_allowed, msg, requires_admin = validate_command(cmd_parts)

        if is_allowed == should_pass and requires_admin == should_require_admin:
            status = "✓"
        else:
            status = "✗"

        print(f"\n{status} Command: {' '.join(cmd_parts[:3])}")
        print(f"  Expected: allowed={should_pass}, admin={should_require_admin}")
        print(f"  Got:      allowed={is_allowed}, admin={requires_admin}")
        if not is_allowed:
            print(f"  Reason:   {msg}")

    print("\n" + "=" * 60)
    print("Self-test complete.")
