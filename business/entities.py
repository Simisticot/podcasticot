from dataclasses import dataclass


@dataclass
class User:
    id: str
    email: str


@dataclass
class LoginCandidate:
    user: User
    password_hash: str
    failed_logins: int


@dataclass
class Subscription:
    user_id: str
    feed_id: str
