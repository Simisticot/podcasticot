from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from time import mktime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class NoAudio(Exception): ...


@dataclass
class EpisodeAssets:
    title: str
    description: Optional[str]
    download_link: Optional[str]
    published_date: datetime
    length: timedelta

    @staticmethod
    def from_feed_entry(entry: dict) -> EpisodeAssets:
        audio_file = next(
            (link for link in entry["links"] if link["type"] == "audio/mpeg"),
            None,
        )
        if audio_file is None:
            raise NoAudio
        download_link = audio_file["href"]
        length = int(audio_file["length"])
        return EpisodeAssets(
            title=entry["title"],
            description=entry.get("summary", None),
            download_link=download_link,
            published_date=datetime.fromtimestamp(mktime(entry["published_parsed"])),
            length=timedelta(seconds=length),
        )


@dataclass
class Episode:
    id: str
    feed_id: str
    assets: EpisodeAssets
    cover_art_url: str


@dataclass
class PlayInfo:
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
