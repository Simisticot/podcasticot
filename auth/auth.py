import hashlib

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

pwd_ctx = PasswordHash(hashers=(Argon2Hasher(),))


def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)


def password_is_valid(password: str, hash: str) -> bool:
    try:
        return pwd_ctx.verify(password=password, hash=hash)
    except ValueError:
        return False


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
