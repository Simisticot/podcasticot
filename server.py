import json
from os import environ as env
from urllib.parse import quote_plus, urlencode

from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for

from datastore import (Datastore, EpisodeNotFound, SubscriptionAlreadyExists,
                       UnknownUser)
from podcast_service import PodcastService
from rss import FeedParserRssParser

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

app = Flask(__name__)
app.secret_key = env.get("APP_SECRET_KEY")


oauth = OAuth(app)

oauth.register(
    "auth0",
    client_id=env.get("AUTH0_CLIENT_ID"),
    client_secret=env.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f'https://{env.get("AUTH0_DOMAIN")}/.well-known/openid-configuration',
)


class PodcastConfiguration:
    @property
    def podcast_service(self) -> PodcastService:
        return PodcastService(
            datastore=Datastore("poddb.db"), rss_parser=FeedParserRssParser()
        )


@app.route("/")
def home():
    return render_template(
        "home.html",
        session=session.get("user"),
        pretty=json.dumps(session.get("user"), indent=4),
    )


@app.route("/podhome")
def podhome():
    session_user = session.get("user")
    if session_user is None:
        return redirect(url_for("login"))
    user_email = session_user["userinfo"]["email"]
    if user_email is None:
        return redirect(url_for("login"))
    podcast_service = PodcastConfiguration().podcast_service
    try:
        db_user = podcast_service.find_user_by_email(user_email=user_email)
    except UnknownUser:
        db_user = podcast_service.save_user(user_email=user_email)
    return render_template(
        template_name_or_list="podcast_home.html",
        episodes=podcast_service.get_user_home_feed(user_id=db_user.id),
    )


@app.post("/subscribe-to-feed")
def subscribe_to_feed():
    session_user = session.get("user")
    if session_user is None:
        return redirect(url_for("login"))
    user_email = session_user["userinfo"]["email"]
    feed_url = request.form["feed"]
    podcast_service = PodcastConfiguration().podcast_service
    try:
        db_user = podcast_service.find_user_by_email(user_email=user_email)
    except UnknownUser:
        db_user = podcast_service.save_user(user_email=user_email)
    try:
        podcast_service.subscribe_user_to_podcast(user_id=db_user.id, feed_url=feed_url)
    except SubscriptionAlreadyExists:
        return "You are already subscribed to this feed", 409
    return render_template(
        template_name_or_list="feed.html",
        episodes=podcast_service.get_user_home_feed(user_id=db_user.id),
    )


@app.post("/play-episode")
def play_episode():
    session_user = session.get("user")
    if session_user is None:
        return redirect(url_for("login"))
    user_email = session_user["userinfo"]["email"]
    podcast_service = PodcastConfiguration().podcast_service
    db_user = podcast_service.find_user_by_email(user_email=user_email)
    if db_user is None:
        return "Unknown User", 404
    try:
        db_user = podcast_service.find_user_by_email(user_email=user_email)
    except UnknownUser:
        db_user = podcast_service.save_user(user_email=user_email)
    episode_id = request.form.get("episode_id", None)
    if episode_id is None:
        return "No episode id provided", 400
    try:
        play_info = podcast_service.get_play_information(
            episode_id=episode_id, user_id=db_user.id
        )
    except EpisodeNotFound:
        return "Episode not found", 404

    rendered = render_template(
        template_name_or_list="player-control.html",
        play_info=play_info,
        play_time_string=play_info.play_time_string(),
    )
    return rendered


@app.post("/current-time/<episode_id>/<seconds>")
def current_time(episode_id: str, seconds: str):
    session_user = session.get("user")
    if session_user is None:
        return redirect(url_for("login"))
    int_seconds = int(seconds)
    user_email = session_user["userinfo"]["email"]
    podcast_service = PodcastConfiguration().podcast_service
    try:
        db_user = podcast_service.find_user_by_email(user_email=user_email)
    except UnknownUser:
        return "Unknown User", 404
    podcast_service.update_current_play_time(
        episode_id=episode_id, user_id=db_user.id, seconds=int_seconds
    )
    return f"Time updated to {seconds} !"


@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token
    return redirect("/podhome")


@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://"
        + env.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("home", _external=True),
                "client_id": env.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=env.get("PORT", 8700))
