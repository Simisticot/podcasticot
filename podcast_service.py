from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from datastore import Datastore
from entities import User
from podcast import Episode, PlayInfo
from rss import RssParser


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
        seconds_played = self.datastore.get_current_time(
            episode_id=episode_id, user_id=user_id
        )
        current_play_time = (
            timedelta(seconds=seconds_played) if seconds_played is not None else None
        )
        return PlayInfo(episode=episode, current_play_time=current_play_time)

    def update_current_play_time(
        self, episode_id: str, user_id: str, seconds: int
    ) -> None:
        self.datastore.set_current_time(
            episode_id=episode_id, user_id=user_id, seconds=seconds
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
