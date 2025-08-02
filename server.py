from os import environ as env
from urllib.parse import quote_plus, urlencode

from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from business.podcast import Episode
from business.podcast_service import PodcastService
from business.rss import FeedParserRssParser
from persistence.datastore import (Datastore, EpisodeNotFound,
                                   SubscriptionAlreadyExists, UnknownUser)

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)


app = Flask(__name__)
app.secret_key = env.get("APP_SECRET_KEY")

if env.get("BEHIND_PROXY") == "yes":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1)

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
            datastore=Datastore("db/poddb.db"), rss_parser=FeedParserRssParser()
        )


@app.route("/")
def home():
    return redirect(url_for("podhome"))


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
    page = request.args.get("page", type=int, default=1)
    play_info = podcast_service.get_latest_listen_play_info(user_id=db_user.id)
    return render_template(
        template_name_or_list="podcast_home.html",
        episodes=podcast_service.get_user_home_feed(user_id=db_user.id, page=page),
        play_info=play_info,
        play_time_string=(
            play_info.previous_listen.play_time_string()
            if play_info is not None and play_info.previous_listen is not None
            else ""
        ),
        page=page,
    )


@app.get("/feed")
def feed():
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
    page = request.args.get("page", type=int, default=1)
    search = request.args.get("search", type=str, default=None)
    return render_template(
        template_name_or_list="feed.html",
        episodes=podcast_service.get_user_home_feed(
            user_id=db_user.id, page=page, search=search
        ),
        page=page,
    )


@app.get("/episode/<episode_id>")
def view_episode_info(episode_id):
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
    episode: Episode = podcast_service.get_episode(
        episode_id=episode_id, user_id=db_user.id
    )
    return render_template(
        template_name_or_list="episode_details.html", episode=episode
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
        episodes=podcast_service.get_user_home_feed(user_id=db_user.id, page=1),
        page=1,
    )


@app.post("/refresh")
def refresh():
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

    podcast_service.update_user_feeds(user_id=db_user.id)
    return render_template(
        template_name_or_list="feed.html",
        episodes=podcast_service.get_user_home_feed(user_id=db_user.id, page=1),
        page=1,
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
        play_time_string=(
            play_info.previous_listen.play_time_string()
            if play_info.previous_listen is not None
            else ""
        ),
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
    session.permanent = True
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
