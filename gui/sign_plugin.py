import argparse
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "ai_assistant_config"

def generate_keys(private_key_path, public_key_path):
    """Generates an RSA private and public key pair and saves them to PEM files."""
    private_key_path = Path(private_key_path)
    public_key_path = Path(public_key_path)

    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.parent.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    private_key_path.write_bytes(pem_private)
    print(f"Private key saved to {private_key_path}")

    public_key = private_key.public_key()
    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    public_key_path.write_bytes(pem_public)
    print(f"Public key saved to {public_key_path}")

def sign_file(private_key_path, file_to_sign):
    """Signs a file with the given private key and creates a .sig file."""
    private_key_path = Path(private_key_path)
    file_to_sign = Path(file_to_sign)

    if not private_key_path.exists():
        print(f"Error: Private key not found at {private_key_path}")
        return
    if not file_to_sign.exists():
        print(f"Error: File to sign not found at {file_to_sign}")
        return

    with open(private_key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(key_file.read(), password=None)

    file_data = file_to_sign.read_bytes()

    signature = private_key.sign(
        file_data,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256()
    )

    signature_file = file_to_sign.with_suffix(file_to_sign.suffix + ".sig")
    signature_file.write_bytes(signature)
    print(f"Signature for {file_to_sign.name} saved to {signature_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plugin Signing Utility for Igris.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 'genkeys' command
    genkeys_parser = subparsers.add_parser("genkeys", help="Generate a new public/private key pair.")
    genkeys_parser.add_argument("--priv", default=str(CONFIG_DIR / "private_key.pem"), help="Path to save the private key.")
    genkeys_parser.add_argument("--pub", default=str(CONFIG_DIR / "public_key.pem"), help="Path to save the public key.")

    # 'sign' command
    sign_parser = subparsers.add_parser("sign", help="Sign a plugin file.")
    sign_parser.add_argument("plugin_file", help="The path to the plugin .py file to sign.")
    sign_parser.add_argument("--key", default=str(CONFIG_DIR / "private_key.pem"), help="Path to the private key to use for signing.")

    args = parser.parse_args()

    if args.command == "genkeys":
        generate_keys(args.priv, args.pub)
    elif args.command == "sign":
        sign_file(args.key, args.plugin_file)