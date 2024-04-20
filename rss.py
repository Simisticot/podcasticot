import feedparser

from podcast import EpisodeAssets


def assets_from_feed_list_chronological(url_list: list[str]) -> list[EpisodeAssets]:
    all_assets = []
    for url in url_list:
        feed = feedparser.parse(url)
        all_assets.extend([EpisodeAssets.from_feed_entry(entry) for entry in feed["entries"]])

    all_assets.sort(reverse=True, key=lambda assets: assets.published_date)

    return all_assets
