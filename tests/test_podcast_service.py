from datetime import datetime, timedelta
from typing import Callable, Optional

import pytest

from persistence.datastore import Datastore, UnknownUser
from business.podcast import EpisodeAssets, PreviousListen
from business.podcast_service import PodcastService
from business.rss import FakeRssParser, PodcastImport


class EpisodeAssetFactory:
    @classmethod
    def build(cls, published_date: Optional[datetime] = None) -> EpisodeAssets:
        if published_date is None:
            published_date = datetime.now()
        return EpisodeAssets(
            title="test title",
            description="test_description",
            download_link="test_download_link",
            published_date=published_date,
            length=timedelta(hours=2),
        )


@pytest.fixture
def service_factory() -> Callable[..., PodcastService]:
    def factory(
        rss_feed_podcasts: Optional[dict[str, PodcastImport]] = None,
    ) -> PodcastService:
        if rss_feed_podcasts is None:
            rss_feed_podcasts = {}
        return PodcastService(
            datastore=Datastore(":memory:"),
            rss_parser=FakeRssParser(imports=rss_feed_podcasts),
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
        rss_feed_podcasts={
            "this matters": PodcastImport(
                episode_assets=[EpisodeAssetFactory.build()],
                cover_art_url="Fake cover url",
            )
        }
    )

    alice = service.save_user("alice@example.com")
    service.subscribe_user_to_podcast(user_id=alice.id, feed_url="this matters")

    alices_feed = service.get_user_home_feed(user_id=alice.id)
    assert len(alices_feed) == 1
    play_info = alices_feed[0]
    assert play_info.episode.assets.title == "test title"
    assert isinstance(play_info.episode.assets.published_date, datetime)


def test_update_single_users_feed(
    service_factory: Callable[..., PodcastService]
) -> None:
    service = service_factory(
        rss_feed_podcasts={
            "this matters": PodcastImport(
                episode_assets=[
                    EpisodeAssetFactory.build(
                        published_date=datetime(year=2000, month=1, day=1),
                    )
                ],
                cover_art_url="Fake cover url",
            ),
            "this is different": PodcastImport(
                episode_assets=[
                    EpisodeAssetFactory.build(
                        published_date=datetime(year=2000, month=1, day=1),
                    )
                ],
                cover_art_url="Fake cover url",
            ),
        }
    )

    alice = service.save_user("alice@example.com")
    bob = service.save_user("bob@example.com")

    service.subscribe_user_to_podcast(user_id=alice.id, feed_url="this matters")
    service.subscribe_user_to_podcast(user_id=bob.id, feed_url="this is different")

    alices_feed = service.get_user_home_feed(user_id=alice.id)
    bobs_feed = service.get_user_home_feed(user_id=bob.id)

    assert len(alices_feed) == 1
    assert len(bobs_feed) == 1

    # add an episode to the fake rss feed
    assert isinstance(service.rss_parser, FakeRssParser)
    service.rss_parser.imports["this matters"].episode_assets.append(
        EpisodeAssetFactory.build(published_date=datetime(year=2000, month=1, day=2)),
    )
    service.rss_parser.imports["this is different"].episode_assets.append(
        EpisodeAssetFactory.build(published_date=datetime(year=2000, month=1, day=2)),
    )

    service.update_user_feeds(user_id=bob.id)

    alices_new_feed = service.get_user_home_feed(user_id=alice.id)
    bobs_new_feed = service.get_user_home_feed(user_id=bob.id)

    assert len(alices_new_feed) == 1
    assert len(bobs_new_feed) == 2


def test_update_all_feeds(service_factory: Callable[..., PodcastService]) -> None:
    service = service_factory(
        rss_feed_podcasts={
            "this matters": PodcastImport(
                episode_assets=[
                    EpisodeAssetFactory.build(
                        published_date=datetime(year=2000, month=1, day=1)
                    )
                ],
                cover_art_url="Fake cover url",
            ),
            "this is different": PodcastImport(
                episode_assets=[
                    EpisodeAssetFactory.build(
                        published_date=datetime(year=2000, month=1, day=1)
                    )
                ],
                cover_art_url="Fake cover url",
            ),
        }
    )

    alice = service.save_user("alice@example.com")
    bob = service.save_user("bob@example.com")

    service.subscribe_user_to_podcast(user_id=alice.id, feed_url="this matters")
    service.subscribe_user_to_podcast(user_id=bob.id, feed_url="this is different")

    alices_feed = service.get_user_home_feed(user_id=alice.id)
    bobs_feed = service.get_user_home_feed(user_id=bob.id)

    assert len(alices_feed) == 1
    assert len(bobs_feed) == 1

    # add an episode to the fake rss feed
    assert isinstance(service.rss_parser, FakeRssParser)
    service.rss_parser.imports["this matters"].episode_assets.append(
        EpisodeAssetFactory.build(published_date=datetime(year=2000, month=1, day=2))
    )
    service.rss_parser.imports["this is different"].episode_assets.append(
        EpisodeAssetFactory.build(published_date=datetime(year=2000, month=1, day=2))
    )

    service.update_all_feeds()

    alices_new_feed = service.get_user_home_feed(user_id=alice.id)
    bobs_new_feed = service.get_user_home_feed(user_id=bob.id)

    assert len(alices_new_feed) == 2
    assert len(bobs_new_feed) == 2


def test_play_info(service_factory: Callable[..., PodcastService]) -> None:
    service = service_factory(
        rss_feed_podcasts={
            "this matters": PodcastImport(
                episode_assets=[
                    EpisodeAssetFactory.build(
                        published_date=datetime(year=2000, month=1, day=1)
                    ),
                    EpisodeAssetFactory.build(
                        published_date=datetime(year=2000, month=1, day=2)
                    ),
                ],
                cover_art_url="Fake cover url",
            ),
        }
    )

    alice = service.save_user("alice@example.com")
    service.subscribe_user_to_podcast(user_id=alice.id, feed_url="this matters")
    alices_feed = service.get_user_home_feed(alice.id)
    play_info = alices_feed[0]
    service.update_current_play_time(
        user_id=alice.id, episode_id=play_info.episode.id, seconds=30
    )
    play_info = service.get_play_information(
        user_id=alice.id, episode_id=play_info.episode.id
    )
    assert play_info.previous_listen is not None
    assert play_info.previous_listen.time_listened == timedelta(seconds=30)

    latest_listen_play_info = service.get_latest_listen_play_info(user_id=alice.id)
    assert latest_listen_play_info == play_info

    other_play_info = alices_feed[1]
    service.update_current_play_time(
        user_id=alice.id, episode_id=other_play_info.episode.id, seconds=3661
    )

    new_latest_listen_play_info = service.get_latest_listen_play_info(user_id=alice.id)
    assert new_latest_listen_play_info is not None
    assert new_latest_listen_play_info != latest_listen_play_info
    assert new_latest_listen_play_info.episode.id == other_play_info.episode.id

    service.update_current_play_time(
        user_id=alice.id, episode_id=play_info.episode.id, seconds=60
    )

    newer_latest_listen_play_info = service.get_latest_listen_play_info(
        user_id=alice.id
    )

    assert newer_latest_listen_play_info is not None
    assert newer_latest_listen_play_info != new_latest_listen_play_info
    assert newer_latest_listen_play_info.episode.id == play_info.episode.id


def test_play_time_string() -> None:
    previous_listen = PreviousListen(
        time_listened=timedelta(seconds=3661), time=datetime.now()
    )
    assert previous_listen.play_time_string() == "#t=1:01:01"
