from dataclasses import dataclass


@dataclass
class User:
    id: str
    email: str

@dataclass
class Subscription:
    user_id: str
    feed_url: str
