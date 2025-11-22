from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from time import mktime
from typing import Optional

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class NoAudio(Exception): ...


@dataclass
class EpisodeAssets:
    title: str
    description: Optional[str]
    download_link: Optional[str]
    published_date: datetime
    length: Optional[int]

    @staticmethod
    def from_feed_entry(entry: dict) -> EpisodeAssets:
        audio_file = next(
            (link for link in entry["links"] if link["type"] == "audio/mpeg"),
            None,
        )
        length = None
        if itunes_duration := entry.get("itunes:duration", None):
            values = itunes_duration.split(":")
            match len(values):
                case 1:
                    length = timedelta(seconds=values[0]).seconds
                case 2:
                    length = timedelta(seconds=values[1], minutes=values[0]).seconds
                case 3:
                    length = timedelta(
                        seconds=values[2], minutes=values[1], hours=values[0]
                    ).seconds
                case _:
                    logger.info(
                        f"Unexpected value for itunes duration : {itunes_duration}"
                    )
        if audio_file is None:
            raise NoAudio
        return EpisodeAssets(
            title=entry["title"],
            description=entry.get("summary", None),
            download_link=audio_file.get("href", None),
            published_date=datetime.fromtimestamp(mktime(entry["published_parsed"])),
            length=length,
        )


@dataclass
class Episode:
    id: str
    feed_id: str
    assets: EpisodeAssets
    cover_art_url: str


class PlayInfo(BaseModel):
    episode: Episode
    previous_listen: Optional[PreviousListen]


@dataclass
class Feed:
    id: str
    url: str
    cover_art_url: str


class PreviousListen(BaseModel):
    time_listened: timedelta
    time: datetime

    def play_time_string(self) -> str:
        return f"#t={str(self.time_listened)}"

    model_config = ConfigDict(ser_json_timedelta="float")
