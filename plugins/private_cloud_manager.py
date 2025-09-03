"""
Private Encrypted Cloud Manager Plugin
- Manages a local "cloud" directory for notes, scripts, etc.
- Encrypts files before uploading them to a secure SFTP server.
- Decrypts files after downloading them from the SFTP server.
"""
from cryptography.fernet import Fernet
from pathlib import Path
import os
import getpass
import tempfile

try:
    import paramiko
except ImportError:
    # This will be caught by the functions that need it, providing a clear error.
    paramiko = None

# --- Configuration ---
try:
    from core.igris_core import ROOT_DIR
except ImportError:
    ROOT_DIR = Path(__file__).resolve().parent.parent

LOCAL_CLOUD_DIR = ROOT_DIR / "private_cloud" / "local"
KEY_FILE = ROOT_DIR / "private_cloud" / "cloud_storage.key"

# --- SFTP Configuration ---
# IMPORTANT: For real use, store these credentials securely, not in the script.
# Consider environment variables, a separate config file, or a secrets manager.
SFTP_CONFIG = {
    "hostname": "YOUR_SFTP_HOSTNAME",  # e.g., "sftp.example.com"
    "port": 22,
    "username": "YOUR_SFTP_USERNAME",
    "password": "",  # Leave blank to be prompted securely at runtime
    "remote_dir": "/igris_cloud_backups" # The directory on the SFTP server
}

# --- Core Functions ---

def get_fernet() -> Fernet:
    """Generates or loads the encryption key and returns a Fernet instance."""
    if not KEY_FILE.exists():
        print("[INFO] No encryption key found. Generating a new one...")
        key = Fernet.generate_key()
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_bytes(key)
        print(f"[SUCCESS] New key saved to: {KEY_FILE}")
    else:
        key = KEY_FILE.read_bytes()
    return Fernet(key)

def get_sftp_client():
    """Establishes an SFTP connection and returns the client and transport."""
    if not paramiko:
        raise ImportError("The 'paramiko' library is required for SFTP. Please run: pip install paramiko")

    transport = paramiko.Transport((SFTP_CONFIG["hostname"], SFTP_CONFIG["port"]))
    
    password = SFTP_CONFIG.get("password") or ""
    if not password:
        password = getpass.getpass(f"Enter SFTP password for {SFTP_CONFIG['username']}: ")
        
    transport.connect(username=SFTP_CONFIG["username"], password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    
    # Ensure remote directory exists
    try:
        sftp.stat(SFTP_CONFIG["remote_dir"])
    except FileNotFoundError:
        print(f"[INFO] Remote directory not found. Creating '{SFTP_CONFIG['remote_dir']}'...")
        sftp.mkdir(SFTP_CONFIG["remote_dir"])
        
    return sftp, transport

def encrypt_file(fernet: Fernet, source_path: Path, dest_path: Path):
    """Encrypts a single file."""
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        data = source_path.read_bytes()
        encrypted_data = fernet.encrypt(data)
        dest_path.write_bytes(encrypted_data)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to encrypt {source_path.name}: {e}")
        return False

def decrypt_file(fernet: Fernet, source_path: Path, dest_path: Path):
    """Decrypts a single file."""
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        encrypted_data = source_path.read_bytes()
        decrypted_data = fernet.decrypt(encrypted_data)
        dest_path.write_bytes(decrypted_data)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to decrypt {source_path.name}: {e}")
        return False

def sync_to_remote():
    """Encrypts and uploads all files from local to the SFTP remote."""
    fernet = get_fernet()
    LOCAL_CLOUD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        sftp, transport = get_sftp_client()
    except Exception as e:
        return f"[ERROR] SFTP Connection Failed: {e}"

    print(f"\n[SYNC] Starting upload to SFTP server: {SFTP_CONFIG['hostname']}...")
    synced_count = 0
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        for local_file in LOCAL_CLOUD_DIR.iterdir():
            if local_file.is_file():
                encrypted_temp_file = temp_path / f"{local_file.name}.encrypted"
                remote_path = f"{SFTP_CONFIG['remote_dir']}/{local_file.name}.encrypted"
                
                print(f"  -> Encrypting {local_file.name}...")
                if encrypt_file(fernet, local_file, encrypted_temp_file):
                    print(f"  -> Uploading to {remote_path}...")
                    try:
                        sftp.put(str(encrypted_temp_file), remote_path)
                        synced_count += 1
                    except Exception as e:
                        print(f"[ERROR] Failed to upload {local_file.name}: {e}")
    
    transport.close()
    return f"[SUCCESS] Upload complete. {synced_count} file(s) synced to SFTP."

def sync_from_remote():
    """Downloads and decrypts all files from the SFTP remote to local."""
    fernet = get_fernet()
    LOCAL_CLOUD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        sftp, transport = get_sftp_client()
    except Exception as e:
        return f"[ERROR] SFTP Connection Failed: {e}"

    print(f"\n[SYNC] Starting download from SFTP server: {SFTP_CONFIG['hostname']}...")
    synced_count = 0
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        try:
            remote_files = sftp.listdir(SFTP_CONFIG["remote_dir"])
        except Exception as e:
            transport.close()
            return f"[ERROR] Could not list remote directory: {e}"

        for remote_filename in remote_files:
            if remote_filename.endswith(".encrypted"):
                local_file_name = remote_filename.replace(".encrypted", "")
                local_file_path = LOCAL_CLOUD_DIR / local_file_name
                remote_file_path = f"{SFTP_CONFIG['remote_dir']}/{remote_filename}"
                encrypted_temp_file = temp_path / remote_filename

                print(f"  -> Downloading {remote_filename}...")
                try:
                    sftp.get(remote_file_path, str(encrypted_temp_file))
                    print(f"  -> Decrypting to {local_file_name}...")
                    if decrypt_file(fernet, encrypted_temp_file, local_file_path):
                        synced_count += 1
                except Exception as e:
                    print(f"[ERROR] Failed to download/decrypt {remote_filename}: {e}")

    transport.close()
    return f"[SUCCESS] Download complete. {synced_count} file(s) synced from SFTP."

def run():
    """Main plugin entry point with a user menu."""
    # Setup initial directories and a sample file if they don't exist
    if not LOCAL_CLOUD_DIR.exists():
        LOCAL_CLOUD_DIR.mkdir(parents=True, exist_ok=True)
        (LOCAL_CLOUD_DIR / "welcome.txt").write_text("Welcome to your private cloud!")

    while True:
        print("\n--- Private Cloud Manager ---")
        print("1. Upload files to cloud (Encrypt & Sync)")
        print("2. Download files from cloud (Sync & Decrypt)")
        print("3. Exit")
        choice = input("Select an option: ").strip()

        if choice == '1':
            print(sync_to_remote())
        elif choice == '2':
            print(sync_from_remote())
        elif choice == '3':
            return "Cloud manager closed."
        else:
            print("[ERROR] Invalid option. Please try again.")

if __name__ == "__main__":
    run()