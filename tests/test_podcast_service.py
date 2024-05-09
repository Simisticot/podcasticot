from datetime import datetime, timedelta
from types import new_class
from typing import Callable, Optional

import pytest

from datastore import Datastore, UnknownUser
from podcast import EpisodeAssets, PreviousListen
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
    assert isinstance(episode.assets.published_date, datetime)


def test_update_feed(service_factory: Callable[..., PodcastService]) -> None:
    service = service_factory(
        rss_feed_episode_assets=[
            EpisodeAssets(
                title="test title",
                description="test_description",
                download_link="test_download_link",
                published_date=datetime(year=2000, month=1, day=1),
            )
        ]
    )

    alice = service.save_user("alice@example.com")
    service.subscribe_user_to_podcast(user_id=alice.id, feed_url="this doesn't matter")

    alices_feed = service.get_user_home_feed(user_id=alice.id)
    assert len(alices_feed) == 1

    # add an episode to the fake rss feed
    assert isinstance(service.rss_parser, FakeRssParser)
    service.rss_parser.assets.append(
        EpisodeAssets(
            title="second_test_title",
            description="second_test_description",
            download_link="second_test_download_link",
            published_date=datetime(year=2000, month=1, day=2),  # a day later
        )
    )

    service.update_all_feeds()

    alices_new_feed = service.get_user_home_feed(user_id=alice.id)

    assert len(alices_new_feed) == 2


def test_play_info(service_factory: Callable[..., PodcastService]) -> None:
    service = service_factory(
        rss_feed_episode_assets=[
            EpisodeAssets(
                title="test title",
                description="test_description",
                download_link="test_download_link",
                published_date=datetime(year=2000, month=1, day=1),
            ),
            EpisodeAssets(
                title="second_test_title",
                description="second_test_description",
                download_link="second_test_download_link",
                published_date=datetime(year=2000, month=1, day=2),
            ),
        ]
    )

    alice = service.save_user("alice@example.com")
    service.subscribe_user_to_podcast(user_id=alice.id, feed_url="this doesn't matter")
    alices_feed = service.get_user_home_feed(alice.id)
    episode = alices_feed[0]
    service.update_current_play_time(
        user_id=alice.id, episode_id=episode.id, seconds=30
    )
    play_info = service.get_play_information(user_id=alice.id, episode_id=episode.id)
    assert play_info.previous_listen is not None
    assert play_info.previous_listen.time_listened == timedelta(seconds=30)

    latest_listen_play_info = service.get_latest_listen_play_info(user_id=alice.id)
    assert latest_listen_play_info == play_info

    other_episode = alices_feed[1]
    service.update_current_play_time(
        user_id=alice.id, episode_id=other_episode.id, seconds=3661
    )

    new_latest_listen_play_info = service.get_latest_listen_play_info(user_id=alice.id)
    assert new_latest_listen_play_info is not None
    assert new_latest_listen_play_info != latest_listen_play_info
    assert new_latest_listen_play_info.episode.id == other_episode.id

    service.update_current_play_time(
        user_id=alice.id, episode_id=episode.id, seconds=60
    )

    newer_latest_listen_play_info = service.get_latest_listen_play_info(
        user_id=alice.id
    )

    assert newer_latest_listen_play_info is not None
    assert newer_latest_listen_play_info != new_latest_listen_play_info
    assert newer_latest_listen_play_info.episode.id == episode.id


def test_play_time_string() -> None:
    previous_listen = PreviousListen(
        time_listened=timedelta(seconds=3661), time=datetime.now()
    )
    assert previous_listen.play_time_string() == "#t=1:01:01"
