import secrets

from utils.security import hash_token


def generate_numeric_otp(length: int = 6) -> str:
    """Cryptographically random numeric OTP (default 6 digits)."""
    if length != 6:
        raise ValueError("Only 6-digit OTP is supported")
    return f"{secrets.randbelow(900000) + 100000:06d}"


def hash_otp(otp: str) -> str:
    return hash_token(otp.strip())
