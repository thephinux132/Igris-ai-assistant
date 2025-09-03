"""
Encrypts the latest security audit file from the /audits directory.
Uses Fernet symmetric encryption.
"""
from cryptography.fernet import Fernet
from pathlib import Path
import os

# Try to import ROOT_DIR for consistent pathing
try:
    from core.igris_core import ROOT_DIR
except ImportError:
    ROOT_DIR = Path(__file__).resolve().parent.parent

AUDITS_DIR = ROOT_DIR / "audits"
KEY_FILE = AUDITS_DIR / "audit_encryption.key"

def run():
    AUDITS_DIR.mkdir(exist_ok=True)

    # Find the most recent unencrypted audit file (.txt)
    try:
        audit_files = sorted(
            [f for f in AUDITS_DIR.glob("security_audit_*.txt") if f.is_file()],
            key=os.path.getmtime,
            reverse=True
        )
        if not audit_files:
            return "[ERROR] No unencrypted audit files found in the /audits directory. Please run a security audit first."

        latest_audit_file = audit_files[0]
    except Exception as e:
        return f"[ERROR] Could not search for audit files: {e}"

    # Generate or reuse encryption key
    if not KEY_FILE.exists():
        key = Fernet.generate_key()
        KEY_FILE.write_bytes(key)
    else:
        key = KEY_FILE.read_bytes()

    fernet = Fernet(key)

    # Encrypt the latest audit file
    try:
        data_to_encrypt = latest_audit_file.read_bytes()
        encrypted_data = fernet.encrypt(data_to_encrypt)

        encrypted_output_path = latest_audit_file.with_suffix(".txt.encrypted")
        encrypted_output_path.write_bytes(encrypted_data)

        # For security, you might want to remove the original unencrypted file.
        # This is commented out by default to be safe.
        # latest_audit_file.unlink()

        return (f"[✓] Successfully encrypted:\n  {latest_audit_file.name}\n"
                f"   -> {encrypted_output_path.name}\n"
                f"Key is stored at: {KEY_FILE}")

    except Exception as e:
        return f"[ERROR] Encryption failed: {e}"
