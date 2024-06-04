from abc import abstractmethod
from dataclasses import dataclass
from typing import Protocol

import feedparser

from business.podcast import EpisodeAssets, NoAudio


@dataclass
class PodcastImport:
    cover_art_url: str
    episode_assets: list[EpisodeAssets]


class RssParser(Protocol):

    @abstractmethod
    def import_feed(self, feed_url: str) -> PodcastImport: ...


class FeedParserRssParser(RssParser):
    def import_feed(self, feed_url: str) -> PodcastImport:
        feed = feedparser.parse(feed_url)
        assets: list[EpisodeAssets] = []
        for entry in feed["entries"]:
            try:
                assets.append(EpisodeAssets.from_feed_entry(entry))
            except NoAudio:
                continue

        return PodcastImport(
            cover_art_url=feed.feed.image["href"], episode_assets=assets
        )


@dataclass
class FakeRssParser(RssParser):
    imports: dict[str, PodcastImport]

    def import_feed(self, feed_url: str) -> PodcastImport:
        podcast_import = self.imports.get(feed_url)
        if podcast_import is None:
            raise RuntimeError("No assets for this url")

        return podcast_import
