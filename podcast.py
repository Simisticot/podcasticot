from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import mktime
from typing import Optional


@dataclass
class EpisodeAssets:
    title: str
    description: Optional[str]
    download_link: Optional[str]
    published_date: datetime

    @staticmethod
    def from_feed_entry(entry: dict) -> EpisodeAssets:
        download_link = next(
            (link["href"] for link in entry["links"] if link["type"] == "audio/mpeg"),
            None,
        )
        return EpisodeAssets(
            title=entry["title"],
            description=entry.get("summary", None),
            download_link=download_link,
            published_date=datetime.fromtimestamp(mktime(entry["published_parsed"])),
        )


@dataclass
class Episode:
    id: str
    assets: EpisodeAssets
