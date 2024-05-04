import feedparser

from podcast import EpisodeAssets


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
