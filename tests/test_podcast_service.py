from datetime import datetime
from typing import Callable, Optional

import pytest

from datastore import Datastore, UnknownUser
from podcast import EpisodeAssets
from podcast_service import PodcastService
from rss import FakeRssParser


@pytest.fixture
def service_factory() -> Callable[..., PodcastService]:
    def factory(
        rss_feed_episode_assets: Optional[list[EpisodeAssets]] = None,
    ) -> PodcastService:
        if rss_feed_episode_assets is None:
            rss_feed_episode_assets = []
        return PodcastService(
            datastore=Datastore(":memory:"),
            rss_parser=FakeRssParser(assets=rss_feed_episode_assets),
        )

    return factory


@pytest.fixture
def service(service_factory: Callable[..., PodcastService]) -> PodcastService:
    return service_factory()


def test_save_and_find_user(service: PodcastService) -> None:
    saved_alice = service.save_user("alice@example.com")
    found_alice = service.find_user_by_email("alice@example.com")
    assert saved_alice == found_alice


def test_find_user_fails_for_nonexistent_user(service: PodcastService) -> None:
    with pytest.raises(UnknownUser):
        service.find_user_by_email("alice@example.com")


def test_subscribe_to_feed(service_factory: Callable[..., PodcastService]) -> None:
    service = service_factory(
        rss_feed_episode_assets=[
            EpisodeAssets(
                title="test title",
                description="test_description",
                download_link="test_download_link",
                published_date=datetime.now(),
            )
        ]
    )

    alice = service.save_user("alice@example.com")
    service.subscribe_user_to_podcast(user_id=alice.id, feed_url="this doesn't matter")

    alices_feed = service.get_user_home_feed(user_id=alice.id)
    assert len(alices_feed) == 1
    episode = alices_feed[0]
    assert episode.assets.title == "test title"
