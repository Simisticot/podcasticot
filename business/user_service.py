from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from auth.auth import hash_password, hash_session_token
from business.entities import LoginCandidate, User
from persistence.datastore import Datastore


class TooManyRegistrations(Exception): ...


@dataclass
class UserService:
    datastore: Datastore

    def find_user_by_email(self, user_email: str) -> User:
        return self.datastore.get_user_by_email(email=user_email)

    def get_login_candidate(self, user_email: str) -> LoginCandidate:
        return self.datastore.get_login_candidate(
            email=user_email,
            failed_login_cutoff=datetime.now(timezone.utc) - timedelta(hours=1),
        )

    def add_failed_login(self, user_id: str) -> None:
        failure_time = datetime.now(timezone.utc)
        self.datastore.add_failed_login(user_id=user_id, failure_time=failure_time)

    def set_user_password(self, user_email: str, new_password: str) -> None:
        user = self.datastore.get_user_by_email(email=user_email)
        self.datastore.delete_all_sessions(user_id=user.id)
        self.datastore.set_user_password(
            user_email=user_email, new_hash=hash_password(password=new_password)
        )

    def delete_all_sessions(self, user_id: str) -> None:
        self.datastore.delete_all_sessions(user_id=user_id)

    def find_user_by_active_session(self, token: str, current_time: datetime) -> User:
        return self.datastore.get_user_from_active_session(
            token_hash=hash_session_token(token), current_time=current_time
        )

    def create_session(
        self, token_hash: str, user_id: str, expires_at: datetime
    ) -> None:
        self.datastore.create_session(
            token_hash=token_hash, user_id=user_id, expires_at=expires_at
        )

    def register_user(self, user_email: str, password_hash: str) -> User:
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        num_accounts_registered_in_last_hour = (
            self.datastore.count_accounts_registered_after(point=hour_ago)
        )

        if num_accounts_registered_in_last_hour > 10:
            raise TooManyRegistrations()

        user_id = str(uuid4())

        return self.datastore.register_user(
            id=user_id,
            email=user_email,
            password_hash=password_hash,
            created_at=now,
        )
