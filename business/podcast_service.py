from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from persistence.datastore import Datastore
from business.entities import User
from business.podcast import Episode, PlayInfo
from business.rss import RssParser


@dataclass
class PodcastService:
    datastore: Datastore
    rss_parser: RssParser

    def find_user_by_email(self, user_email: str) -> User:
        return self.datastore.get_user_by_email(email=user_email)

    def save_user(self, user_email: str) -> User:
        user_id = str(uuid4())
        return self.datastore.save_user(id=user_id, email=user_email)

    def get_user_home_feed(self, user_id: str) -> list[Episode]:
        return self.datastore.get_user_feeds(user_id)

    def subscribe_user_to_podcast(self, user_id: str, feed_url: str) -> None:
        assets = self.rss_parser.get_assets_from_feed(feed_url)
        feed_id = str(uuid4())
        self.datastore.save_feed(feed_id=feed_id, episodes=assets)
        self.datastore.subscribe(user_id=user_id, feed_url=feed_url, feed_id=feed_id)

    def get_episode(self, episode_id: str) -> Episode:
        episode = self.datastore.get_episode(episode_id=episode_id)
        return episode

    def get_play_information(self, episode_id: str, user_id: str) -> PlayInfo:
        episode = self.datastore.get_episode(episode_id=episode_id)
        previous_listen = self.datastore.get_previous_listen(
            user_id=user_id, episode_id=episode_id
        )
        return PlayInfo(episode=episode, previous_listen=previous_listen)

    def update_current_play_time(
        self, episode_id: str, user_id: str, seconds: int
    ) -> None:
        self.datastore.set_current_time(
            episode_id=episode_id, user_id=user_id, seconds=seconds, time=datetime.now()
        )

    def update_all_feeds(self) -> None:
        feeds = self.datastore.get_all_feeds()
        for feed in feeds:
            feed_episode_assets = self.rss_parser.get_assets_from_feed(
                feed_url=feed.url
            )
            feed_latest_episode = self.datastore.get_latest_episode(feed_id=feed.id)
            new_episode_assets = [
                episode
                for episode in feed_episode_assets
                if episode.published_date > feed_latest_episode.assets.published_date
            ]
            self.datastore.save_feed(feed_id=feed.id, episodes=new_episode_assets)

    def get_latest_listen_play_info(self, user_id: str) -> Optional[PlayInfo]:
        return self.datastore.get_latest_listen_play_info(user_id)
