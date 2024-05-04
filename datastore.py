import sqlite3
from typing import Optional
from uuid import uuid4

from entities import Subscription, User
from podcast import Episode, EpisodeAssets


class UserAlreadyExists(Exception): ...


class SubscriptionAlreadyExists(Exception): ...


class EpisodeNotFound(Exception): ...


class Datastore:

    def __init__(self) -> None:
        self._init_database()

    @staticmethod
    def _init_database():
        connection = sqlite3.connect("poddb.db")
        cursor = connection.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS user (id TEXT NOT NULL PRIMARY KEY, email TEXT UNIQUE );"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS subscription (user_id TEXT NOT NULL, feed_id TEXT NOT NULL, PRIMARY KEY (user_id, feed_id), FOREIGN KEY (user_id) REFERENCES user(id));"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS episode (episode_id TEXT NOT NULL PRIMARY KEY, title TEXT, description TEXT, download_link TEXT, published_date TIMESTAMP NOT NULL, feed_id TEXT NOT NULL, FOREIGN KEY (feed_id) REFERENCES subscription(feed_id));"
        )


    def _get_connection(self):
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

    def subscribe(self, user_id: str, feed_id: str) -> None:
        connection = self._get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO subscription (user_id, feed_id) VALUES (?, ?);",
                (user_id, feed_id),
            )
        except sqlite3.IntegrityError:
            raise SubscriptionAlreadyExists
        connection.commit()
        connection.close()

    def find_subscriptions(self, user_id: str) -> list[Subscription]:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT feed_id FROM subscription WHERE user_id = ?;", (user_id,)
        )
        result = cursor.fetchall()
        connection.close()
        return [Subscription(user_id=user_id, feed_id=row[0]) for row in result]

    def save_feed(self, episodes: list[EpisodeAssets]) -> str:
        connection = self._get_connection()
        cursor = connection.cursor()
        feed_id = str(uuid4())
        episodes_data = [
            (
                str(uuid4()),
                ep.title,
                ep.description,
                ep.download_link,
                ep.published_date,
                feed_id,
            )
            for ep in episodes
        ]
        cursor.executemany(
            "INSERT INTO episode (episode_id, title, description, download_link, published_date, feed_id) values (?,?,?,?,?,?)",
            episodes_data,
        )
        connection.commit()
        connection.close()
        return feed_id

    def get_user_feeds(self, user_id: str) -> list[Episode]:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT episode.episode_id, episode.title, episode.description, episode.download_link, episode.published_date FROM episode JOIN subscription ON episode.feed_id = subscription.feed_id WHERE subscription.user_id = ? ORDER BY episode.published_date DESC LIMIT 10;",
            (user_id,),
        )
        result = cursor.fetchall()
        connection.close()
        episodes = [
            Episode(
                id=row[0],
                assets=EpisodeAssets(
                    title=row[1],
                    description=row[2],
                    download_link=row[3],
                    published_date=row[4],
                ),
            )
            for row in result
        ]
        return episodes

    def get_episode(self, episode_id: str) -> Episode:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "select title, description, download_link, published_date from episode where episode_id = ?;",
            (episode_id,),
        )
        result = cursor.fetchone()
        if len(result) == 0:
            raise EpisodeNotFound

        assets = EpisodeAssets(
            title=result[0],
            description=result[1],
            download_link=result[2],
            published_date=result[3],
        )
        return Episode(id=episode_id, assets=assets)
