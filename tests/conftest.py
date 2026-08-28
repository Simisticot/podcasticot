import sqlite3
from pathlib import Path
from typing import Callable, Optional

import pytest

from business.entities import User
from business.podcast_service import PodcastService
from business.rss import FakeRssParser, PodcastImport
from business.user_service import UserService
from persistence.datastore import Datastore
from persistence.migration import migrate


@pytest.fixture
def service_factory(db_connection: sqlite3.Connection) -> Callable[..., PodcastService]:
    def factory(
        rss_feed_podcasts: Optional[dict[str, PodcastImport]] = None,
    ) -> PodcastService:
        if rss_feed_podcasts is None:
            rss_feed_podcasts = {}
        return PodcastService(
            datastore=Datastore(connection=db_connection),
            rss_parser=FakeRssParser(imports=rss_feed_podcasts),
        )

    return factory


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "podcasticot_test.db"


@pytest.fixture
def db_connection(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    migrate(connection)
    return connection


@pytest.fixture
def service(service_factory: Callable[..., PodcastService]) -> PodcastService:
    return service_factory()


@pytest.fixture
def user_service(db_connection: sqlite3.Connection) -> UserService:
    return UserService(datastore=Datastore(connection=db_connection))


@pytest.fixture
def alice(user_service: UserService) -> User:
    return user_service.register_user(
        password_hash="fake_hash", user_email="alice@example.com"
    )


@pytest.fixture
def bob(user_service: UserService) -> User:
    return user_service.register_user(
        password_hash="fake_hash", user_email="bob@example.com"
    )
