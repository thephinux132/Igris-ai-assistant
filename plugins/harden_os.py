"""
Harden OS Configurations Plugin
- Implements OS hardening techniques via PowerShell and other tools.
"""
import subprocess
import platform
from core.igris_core import run_shell

def run():
    report = []
    os_type = platform.system()

    if os_type == "Windows":
        # 1. Disable SMBv1 (critical security vulnerability)
        try:
            rc, out, err = run_shell("powershell -Command \"Get-WindowsOptionalFeature -Online -FeatureName SMB1Protocol | Where-Object { $_.State -ne 'Disabled' } | ForEach-Object { Disable-WindowsOptionalFeature -Online -FeatureName $_.FeatureName -Remove -NoRestart }\"")
            if rc == 0:
                report.append("[SMBv1] Successfully disabled SMBv1.")
            else:
                # Exit code 3010 means a reboot is required, which is a success for us.
                if "3010" in str(err) or "3010" in str(out):
                     report.append("[SMBv1] Successfully disabled SMBv1. A reboot is required to complete the change.")
                else:
                     report.append(f"[SMBv1] Could not disable SMBv1. It may already be disabled. Details: {err or out}")
        except Exception as e:
            report.append(f"[SMBv1] Error disabling SMBv1: {e}")

        # 2. Disable Guest Account
        try:
            rc, out, err = run_shell("net user guest /active:no")
            if rc == 0:
                report.append("[Guest Account] Successfully disabled the guest account.")
            else:
                report.append(f"[Guest Account] Failed to disable guest account: {err or out}")
        except Exception as e:
            report.append(f"[Guest Account] Error disabling guest account: {e}")

        # 3. Enable Windows Defender Firewall for all profiles
        try:
            rc, out, err = run_shell("netsh advfirewall set allprofiles state on")
            if rc == 0:
                report.append("[Firewall] Successfully enabled Windows Defender Firewall for all profiles.")
            else:
                report.append(f"[Firewall] Failed to enable Windows Defender Firewall: {err or out}")
        except Exception as e:
            report.append(f"[Firewall] Error enabling Windows Defender Firewall: {e}")
    else:
        report.append("[OS Hardening] Hardening steps are only implemented for Windows at this time.")

    return "\n".join(report)

if __name__ == "__main__":
    print(run())