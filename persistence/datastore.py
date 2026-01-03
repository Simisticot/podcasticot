import sqlite3
from datetime import datetime
from sqlite3 import Connection
from typing import Optional
from uuid import uuid4

from business.entities import Subscription, User
from business.podcast import Episode, EpisodeAssets, Feed, PlayInfo, PreviousListen


class UserAlreadyExists(Exception): ...


class SubscriptionAlreadyExists(Exception): ...


class EpisodeNotFound(Exception): ...


class UnknownUser(Exception): ...


class Datastore:
    def __init__(self, db_string: str) -> None:
        self.db_string: str = db_string
        self.connection = sqlite3.connect(self.db_string)
        self._init_database()

    def _init_database(self) -> None:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS user (id TEXT NOT NULL PRIMARY KEY, email TEXT UNIQUE );"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS subscription (user_id TEXT NOT NULL, feed_id TEXT NOT NULL, PRIMARY KEY (user_id, feed_id), FOREIGN KEY (user_id) REFERENCES user(id), FOREIGN KEY (feed_id) REFERENCES podcast_feed(id));"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS podcast_feed (id TEXT NOT NULL PRIMARY KEY, feed_url TEXT NOT NULL, cover_art_url TEXT);"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS episode (episode_id TEXT NOT NULL PRIMARY KEY, title TEXT, description TEXT, download_link TEXT, published_date INTEGER NOT NULL, feed_id TEXT NOT NULL, length INTEGER, FOREIGN KEY (feed_id) REFERENCES subscription(feed_id));"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS previous_listen (episode_id TEXT NOT NULL, user_id TEXT NOT NULL, seconds INT NOT NULL, time INT, PRIMARY KEY (episode_id, user_id), FOREIGN KEY (episode_id) REFERENCES episode(episode_id), FOREIGN KEY (user_id) REFERENCES user(id));"
        )

    def _get_connection(self) -> Connection:
        return self.connection

    def save_user(self, id: str, email: str) -> User:
        connection = self._get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("INSERT INTO user (id, email) VALUES (?, ?);", (id, email))
        except sqlite3.IntegrityError:
            raise UserAlreadyExists
        connection.commit()
        return User(id=id, email=email)

    def get_user_by_email(self, email: str) -> User:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM user WHERE email = ?;", (email,))
        result = cursor.fetchone()
        if result is None:
            raise UnknownUser
        return User(id=result[0], email=result[1])

    def subscribe(self, user_id: str, feed_id: str) -> None:
        connection = self._get_connection()
        cursor = connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO subscription (user_id, feed_id) VALUES (?,?);",
                (user_id, feed_id),
            )
        except sqlite3.IntegrityError:
            raise SubscriptionAlreadyExists
        connection.commit()

    def find_subscriptions(self, user_id: str) -> list[Subscription]:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT feed_id FROM subscription WHERE user_id = ?;", (user_id,)
        )
        result = cursor.fetchall()
        return [Subscription(user_id=user_id, feed_id=row[0]) for row in result]

    def save_podcast_feed(
        self, feed_id: str, feed_url: str, cover_art_url: str
    ) -> None:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "insert into podcast_feed (id, feed_url, cover_art_url) values (?,?,?);",
            (
                feed_id,
                feed_url,
                cover_art_url,
            ),
        )
        connection.commit()

    def save_episodes(self, feed_id: str, episodes: list[EpisodeAssets]) -> str:
        connection = self._get_connection()
        cursor = connection.cursor()
        episodes_data = [
            (
                str(uuid4()),
                ep.title,
                ep.description,
                ep.download_link,
                ep.published_date.timestamp(),
                feed_id,
                ep.length,
            )
            for ep in episodes
        ]
        cursor.executemany(
            "INSERT INTO episode (episode_id, title, description, download_link, published_date, feed_id, length) values (?,?,?,?,?,?,?)",
            episodes_data,
        )
        connection.commit()
        return feed_id

    def get_single_feed(
        self, user_id: str, feed_id: str, number_of_episodes: int, page: int
    ) -> list[PlayInfo]:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "SELECT episode.episode_id, episode.feed_id, episode.title, episode.description, episode.download_link, episode.published_date, episode.length, podcast_feed.cover_art_url, previous_listen.seconds, previous_listen.time FROM episode JOIN subscription ON episode.feed_id = subscription.feed_id join podcast_feed on podcast_feed.id = subscription.feed_id LEFT JOIN previous_listen on episode.episode_id = previous_listen.episode_id AND previous_listen.user_id = ? WHERE subscription.user_id = ? AND episode.feed_id = ? ORDER BY episode.published_date DESC LIMIT ? OFFSET ?;",
            (
                user_id,
                user_id,
                feed_id,
                number_of_episodes,
                number_of_episodes * (page - 1),
            ),
        )
        result = cursor.fetchall()
        episodes: list[PlayInfo] = []
        for row in result:
            if row[7] is None or row[8] is None:
                previous_listen = None
            else:
                previous_listen = PreviousListen(
                    time_listened=row[8],
                    time=datetime.fromtimestamp(row[9]),
                )
            episodes.append(
                PlayInfo(
                    previous_listen=previous_listen,
                    episode=Episode(
                        id=row[0],
                        feed_id=row[1],
                        assets=EpisodeAssets(
                            title=row[2],
                            description=row[3],
                            download_link=row[4],
                            published_date=datetime.fromtimestamp(row[5]),
                            length=row[6],
                        ),
                        cover_art_url=row[7],
                    ),
                )
            )
        return episodes

    def get_user_home_feed(
        self,
        user_id: str,
        number_of_episodes: int,
        page: int,
        search: Optional[str],
        include_finished: Optional[bool],
    ) -> list[PlayInfo]:
        connection = self._get_connection()
        cursor = connection.cursor()
        if not search:
            cursor.execute(
                "SELECT episode.episode_id, episode.feed_id, episode.title, episode.description, episode.download_link, episode.published_date, episode.length, podcast_feed.cover_art_url, previous_listen.seconds, previous_listen.time FROM episode JOIN subscription ON episode.feed_id = subscription.feed_id join podcast_feed on podcast_feed.id = subscription.feed_id LEFT JOIN previous_listen on episode.episode_id = previous_listen.episode_id AND previous_listen.user_id = ? WHERE subscription.user_id = ? ORDER BY episode.published_date DESC LIMIT ? OFFSET ?;",
                (user_id, user_id, number_of_episodes, number_of_episodes * (page - 1)),
            )
        else:
            formatted_search = f"%{search}%"
            cursor.execute(
                "SELECT episode.episode_id, episode.feed_id, episode.title, episode.description, episode.download_link, episode.published_date, episode.length, podcast_feed.cover_art_url, previous_listen.seconds, previous_listen.time FROM episode JOIN subscription ON episode.feed_id = subscription.feed_id join podcast_feed on podcast_feed.id = subscription.feed_id LEFT JOIN previous_listen on episode.episode_id = previous_listen.episode_id AND previous_listen.user_id = ? WHERE subscription.user_id = ? AND (episode.description LIKE ? OR episode.title LIKE ?) ORDER BY episode.published_date DESC LIMIT ? OFFSET ?;",
                (
                    user_id,
                    user_id,
                    formatted_search,
                    formatted_search,
                    number_of_episodes,
                    number_of_episodes * (page - 1),
                ),
            )
        result = cursor.fetchall()
        episodes: list[PlayInfo] = []
        for row in result:
            if row[8] is None or row[9] is None:
                previous_listen = None
            else:
                previous_listen = PreviousListen(
                    time_listened=row[8],
                    time=datetime.fromtimestamp(row[9]),
                )
            episodes.append(
                PlayInfo(
                    previous_listen=previous_listen,
                    episode=Episode(
                        id=row[0],
                        feed_id=row[1],
                        assets=EpisodeAssets(
                            title=row[2],
                            description=row[3],
                            download_link=row[4],
                            published_date=datetime.fromtimestamp(row[5]),
                            length=row[6],
                        ),
                        cover_art_url=row[7],
                    ),
                )
            )
        if not include_finished:
            episodes = [
                ep
                for ep in episodes
                if ep.previous_listen is None
                or (
                    ep.episode.assets.length is not None
                    and ep.episode.assets.length
                    - ep.previous_listen.time_listened.seconds
                    >= 20
                )
            ]
        return episodes

    def get_episode(self, episode_id: str, user_id: str) -> Episode:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "select title, episode.feed_id, description, download_link, published_date, length, podcast_feed.cover_art_url from episode join podcast_feed on podcast_feed.id = episode.feed_id join subscription on subscription.feed_id = podcast_feed.id where episode_id = ? and subscription.user_id = ?;",
            (
                episode_id,
                user_id,
            ),
        )
        result = cursor.fetchone()
        if result is None:
            raise EpisodeNotFound

        assets = EpisodeAssets(
            title=result[0],
            description=result[2],
            download_link=result[3],
            published_date=datetime.fromtimestamp(result[4]),
            length=result[5],
        )
        return Episode(
            id=episode_id, feed_id=result[1], assets=assets, cover_art_url=result[6]
        )

    def set_current_time(
        self, episode_id: str, user_id: str, seconds: int, time: datetime
    ) -> None:
        connection = self._get_connection()
        cursor = connection.cursor()
        time_timestamp = time.timestamp()
        cursor.execute(
            "insert into previous_listen (episode_id, user_id, seconds, time) values (?,?,?,?) on conflict(episode_id, user_id) do update set seconds=?, time=?",
            (episode_id, user_id, seconds, time_timestamp, seconds, time_timestamp),
        )
        connection.commit()

    def get_previous_listen(
        self, user_id: str, episode_id: str
    ) -> Optional[PreviousListen]:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "select seconds, time from previous_listen where user_id = ? and episode_id = ?;",
            (user_id, episode_id),
        )
        result = cursor.fetchone()
        if result is None:
            return None
        return PreviousListen(
            time_listened=result[0],
            time=datetime.fromtimestamp(result[1]),
        )

    def get_latest_listen_play_info(self, user_id: str) -> Optional[PlayInfo]:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "select episode.episode_id, episode.feed_id, episode.title, episode.description, episode.download_link, episode.published_date, episode.length, previous_listen.seconds, previous_listen.time, podcast_feed.cover_art_url from previous_listen join episode on previous_listen.episode_id = episode.episode_id join podcast_feed on podcast_feed.id = episode.feed_id where previous_listen.user_id = ? order by previous_listen.time desc limit 1;",
            (user_id,),
        )
        result = cursor.fetchone()
        if result is None:
            return None

        play_info = PlayInfo(
            episode=Episode(
                id=result[0],
                feed_id=result[1],
                assets=EpisodeAssets(
                    title=result[2],
                    description=result[3],
                    download_link=result[4],
                    published_date=datetime.fromtimestamp(result[5]),
                    length=result[6],
                ),
                cover_art_url=result[9],
            ),
            previous_listen=PreviousListen(
                time_listened=result[7],
                time=datetime.fromtimestamp(result[8]),
            ),
        )
        return play_info

    def get_user_subscribed_feeds(self, user_id) -> list[Feed]:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "select podcast_feed.id, podcast_feed.feed_url, podcast_feed.cover_art_url from subscription join podcast_feed on subscription.feed_id = podcast_feed.id where user_id = ?;",
            (user_id,),
        )
        result = cursor.fetchall()
        feeds = [Feed(id=row[0], url=row[1], cover_art_url=row[2]) for row in result]
        return feeds

    def get_all_feeds(self) -> list[Feed]:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute("select id, feed_url, cover_art_url from podcast_feed; ")
        result = cursor.fetchall()
        feeds = [Feed(id=row[0], url=row[1], cover_art_url=row[2]) for row in result]
        return feeds

    def get_latest_episode(self, feed_id: str) -> Episode:
        connection = self._get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "select episode_id, episode.feed_id, title, description ,download_link, published_date, length, podcast_feed.cover_art_url from episode join podcast_feed on episode.feed_id = podcast_feed.id where feed_id = ? order by published_date desc limit 1;",
            (feed_id,),
        )
        result = cursor.fetchone()
        if result is None:
            raise EpisodeNotFound
        episode = Episode(
            id=result[0],
            feed_id=result[1],
            assets=EpisodeAssets(
                title=result[2],
                description=result[3],
                download_link=result[4],
                published_date=datetime.fromtimestamp(result[5]),
                length=result[6],
            ),
            cover_art_url=result[7],
        )
        return episode

    def update_lengths(self, updated_assets: list[EpisodeAssets], feed_id: str) -> None:
        connection = self._get_connection()
        cursor = connection.cursor()
        updates = [(asset.length, asset.title, feed_id) for asset in updated_assets]
        cursor.executemany(
            "update episode set length = ? where title = ? and feed_id = ?;",
            updates,
        )
        connection.commit()

    def update_links(self, updated_assets: list[EpisodeAssets], feed_id: str) -> None:
        connection = self._get_connection()
        cursor = connection.cursor()
        updates = [
            (
                asset.download_link,
                asset.title,
                feed_id,
            )
            for asset in updated_assets
        ]
        cursor.executemany(
            "update episode set download_link = ? where title = ? and feed_id = ?;",
            updates,
        )
        connection.commit()
