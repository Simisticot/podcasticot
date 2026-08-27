import sqlite3
from pathlib import Path
from typing import Callable, Optional

import pytest

from business.podcast_service import PodcastService
from business.rss import FakeRssParser, PodcastImport
from persistence.datastore import Datastore
from persistence.migration import migrate


@pytest.fixture
def service_factory(db_path: Path) -> Callable[..., PodcastService]:
    def factory(
        rss_feed_podcasts: Optional[dict[str, PodcastImport]] = None,
    ) -> PodcastService:
        if rss_feed_podcasts is None:
            rss_feed_podcasts = {}
        connection = sqlite3.connect(db_path)
        migrate(connection)
        return PodcastService(
            datastore=Datastore(connection=connection),
            rss_parser=FakeRssParser(imports=rss_feed_podcasts),
        )

    return factory


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "podcasticot_test.db"


@pytest.fixture
def service(service_factory: Callable[..., PodcastService]) -> PodcastService:
    return service_factory()
