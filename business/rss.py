from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

import feedparser

from business.podcast import EpisodeAssets


def assets_from_feed(url: str) -> list[EpisodeAssets]:
    feed = feedparser.parse(url)
    assets = [EpisodeAssets.from_feed_entry(entry) for entry in feed["entries"]]
    return assets


def assets_from_feed_list_chronological(url_list: list[str]) -> list[EpisodeAssets]:
    all_assets = []
    for url in url_list:
        all_assets.extend(assets_from_feed(url))

    all_assets.sort(reverse=True, key=lambda assets: assets.published_date)

    return all_assets


class RssParser(Protocol):

    @abstractmethod
    def get_assets_from_feed(
        self, feed_url: str
    ) -> list[EpisodeAssets]: ...  # pragma : nocover


class FeedParserRssParser(RssParser):
    def get_assets_from_feed(self, feed_url: str) -> list[EpisodeAssets]:
        return assets_from_feed(url=feed_url)


@dataclass
class FakeRssParser(RssParser):
    assets: dict[str, list[EpisodeAssets]]

    def get_assets_from_feed(self, feed_url: str) -> list[EpisodeAssets]:
        assets = self.assets.get(feed_url)
        if assets is None:
            raise RuntimeError("No assets for this url")

        return assets.copy()
