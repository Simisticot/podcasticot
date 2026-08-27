import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from auth.auth import hash_password, hash_session_token
from business.entities import LoginCandidate, User
from business.podcast import Episode, Feed, PlayInfo
from business.rss import RssParser
from persistence.datastore import Datastore

logger = logging.getLogger(__name__)


class TooManyRegistrations(Exception): ...


@dataclass
class PodcastService:
    datastore: Datastore
    rss_parser: RssParser

    # TODO: spint out user/session management to dedicated service

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

    def get_user_home_feed(
        self,
        user_id: str,
        page: int,
        search: Optional[str] = None,
        chronological: bool = False,
        include_finished: Optional[bool] = False,
    ) -> list[PlayInfo]:
        logger.info("fetching home feed")
        return self.datastore.get_user_home_feed(
            user_id=user_id,
            number_of_episodes=10,
            page=page,
            search=search,
            include_finished=include_finished,
            chronological=chronological,
        )

    def get_single_feed(
        self, user_id: str, page: int, feed_id: str, chronological: bool = False
    ) -> list[PlayInfo]:
        return self.datastore.get_single_feed(
            user_id=user_id,
            feed_id=feed_id,
            number_of_episodes=10,
            page=page,
            chronological=chronological,
        )

    def subscribe_user_to_podcast(self, user_id: str, feed_url: str) -> None:
        podcast = self.rss_parser.import_feed(feed_url)
        feed_id = str(uuid4())
        self.datastore.save_episodes(feed_id=feed_id, episodes=podcast.episode_assets)
        self.datastore.save_podcast_feed(
            feed_id=feed_id,
            feed_url=feed_url,
            cover_art_url=podcast.cover_art_url,
            title=podcast.title,
        )
        self.datastore.subscribe(user_id=user_id, feed_id=feed_id)

    def get_episode(self, episode_id: str, user_id: str) -> Episode:
        episode = self.datastore.get_episode(episode_id=episode_id, user_id=user_id)
        return episode

    def get_play_information(self, episode_id: str, user_id: str) -> PlayInfo:
        episode = self.datastore.get_episode(episode_id=episode_id, user_id=user_id)
        previous_listen = self.datastore.get_previous_listen(
            user_id=user_id, episode_id=episode_id
        )
        return PlayInfo(episode=episode, previous_listen=previous_listen)

    def update_current_play_time(
        self, episode_id: str, user_id: str, seconds: int
    ) -> None:
        self.datastore.set_current_time(
            episode_id=episode_id,
            user_id=user_id,
            seconds=seconds,
            time=datetime.now(timezone.utc),
        )

    def update_user_feeds(self, user_id: str) -> None:
        feeds = self.datastore.get_user_subscribed_feeds(user_id)
        self._update_feeds(feeds)

    def _update_feeds(self, feeds: list[Feed]) -> None:
        for feed in feeds:
            podcast = self.rss_parser.import_feed(feed_url=feed.url)
            feed_latest_episode = self.datastore.get_latest_episode(feed_id=feed.id)
            new_episode_assets = [
                episode
                for episode in podcast.episode_assets
                if episode.published_date > feed_latest_episode.assets.published_date
            ]
            self.datastore.save_episodes(feed_id=feed.id, episodes=new_episode_assets)

            self.datastore.update_links(podcast.episode_assets, feed.id)
            self.datastore.update_lengths(podcast.episode_assets, feed.id)

            if (
                feed.cover_art_url != podcast.cover_art_url
                or feed.title != podcast.title
            ):
                self.datastore.update_podcast_feed(
                    title=podcast.title,
                    cover_art_url=podcast.cover_art_url,
                    feed_url=feed.url,
                    feed_id=feed.id,
                )

    def update_all_feeds(self) -> None:
        feeds = self.datastore.get_all_feeds()
        self._update_feeds(feeds)

    def get_latest_listen_play_info(self, user_id: str) -> Optional[PlayInfo]:
        return self.datastore.get_latest_listen_play_info(user_id)

    def get_user_subscribed_feeds(self, user_id: str) -> list[Feed]:
        return self.datastore.get_user_subscribed_feeds(user_id)
