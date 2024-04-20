import sqlite3
from typing import Optional

from entities import User, Subscription


class UserAlreadyExists(Exception): ...


class SubscriptionAlreadyExists(Exception):
    ...


class Datastore:

    def _get_connection(self):
        connection = sqlite3.connect("poddb.db")
        cursor = connection.cursor()
        res = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user';"
        )
        if res.fetchone() is None:
            cursor.execute(
                "CREATE TABLE user (id TEXT NOT NULL PRIMARY KEY, email TEXT UNIQUE );"
            )
            cursor.execute(
                "CREATE TABLE subscription (user_id TEXT NOT NULL, feed_url TEXT NOT NULL, PRIMARY KEY (user_id, feed_url), FOREIGN KEY (user_id) REFERENCES user(id));"
            )
        connection.close()

        return sqlite3.connect("poddb.db")

    def save_user(self, id: str, email: str) -> User:
        connection = self._get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("INSERT INTO user (id, email) VALUES (?, ?);", (id, email))
        except sqlite3.IntegrityError:
            raise UserAlreadyExists
        connection.commit()
        connection.close()
        return User(id=id, email=email)

    def find_user(self, email: str) -> Optional[User]:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM user WHERE email = ?;", (email,))
        result = cursor.fetchone()
        connection.close()
        if result is None:
            return None
        return User(id=result[0], email=result[1])

    def subscribe(self, user_id: str, feed_url: str) -> None:
        connection = self._get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("INSERT INTO subscription (user_id, feed_url) VALUES (?, ?);", (user_id, feed_url))
        except sqlite3.IntegrityError:
            raise SubscriptionAlreadyExists
        connection.commit()
        connection.close()

    def find_subscriptions(self, user_id: str) -> list[Subscription]:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT feed_url FROM subscription WHERE user_id = ?;", (user_id,))
        result = cursor.fetchall()
        connection.close()
        return [Subscription(user_id=user_id, feed_url=row[0]) for row in result]