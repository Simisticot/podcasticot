from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from business.entities import User
from business.podcast import Episode, Feed, PlayInfo
from business.rss import RssParser
from persistence.datastore import Datastore


@dataclass
class PodcastService:
    datastore: Datastore
    rss_parser: RssParser

    def find_user_by_email(self, user_email: str) -> User:
        return self.datastore.get_user_by_email(email=user_email)

    def save_user(self, user_email: str) -> User:
        user_id = str(uuid4())
        return self.datastore.save_user(id=user_id, email=user_email)

    def get_user_home_feed(self, user_id: str, page: int) -> list[PlayInfo]:
        return self.datastore.get_user_home_feed(
            user_id=user_id, number_of_episodes=10, page=page
        )

    def subscribe_user_to_podcast(self, user_id: str, feed_url: str) -> None:
        podcast = self.rss_parser.import_feed(feed_url)
        feed_id = str(uuid4())
        self.datastore.save_episodes(feed_id=feed_id, episodes=podcast.episode_assets)
        self.datastore.save_podcast_feed(
            feed_id=feed_id, feed_url=feed_url, cover_art_url=podcast.cover_art_url
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
            episode_id=episode_id, user_id=user_id, seconds=seconds, time=datetime.now()
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

    def update_all_feeds(self) -> None:
        feeds = self.datastore.get_all_feeds()
        self._update_feeds(feeds)

    def get_latest_listen_play_info(self, user_id: str) -> Optional[PlayInfo]:
        return self.datastore.get_latest_listen_play_info(user_id)
