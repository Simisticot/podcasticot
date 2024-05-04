import json
from os import environ as env
from urllib.parse import quote_plus, urlencode
from uuid import uuid4

from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for

from datastore import Datastore, EpisodeNotFound, SubscriptionAlreadyExists
from rss import assets_from_feed

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
    ds = Datastore()
    db_user = ds.find_user(user_email)
    if db_user is None:
        db_user = ds.save_user(id=str(uuid4()), email=user_email)
    return render_template(
        template_name_or_list="podcast_home.html",
        episodes=ds.get_user_feeds(db_user.id),
    )


@app.route("/fetch-feeds", methods=["GET", "POST"])
def fetch_feeds():
    session_user = session.get("user")
    if session_user is None:
        return redirect(url_for("login"))
    user_email = session_user["userinfo"]["email"]
    feed_list = request.form["feed_list"].split("\n")
    ds = Datastore()
    db_user = ds.find_user(user_email)
    if db_user is None:
        db_user = ds.save_user(id=str(uuid4()), email=user_email)
    for feed in feed_list:
        feed_id = str(uuid4())
        try:
            ds.subscribe(user_id=db_user.id, feed_id=feed_id, feed_url=feed)
        except SubscriptionAlreadyExists:
            return "You are already subscribed to this feed", 409
        episodes = assets_from_feed(feed)
        ds.save_feed(feed_id, episodes)
    return render_template(
        template_name_or_list="feed.html",
        episodes=ds.get_user_feeds(user_id=db_user.id),
    )


@app.post("/play-episode")
def play_episode():
    episode_id = request.form.get("episode_id", None)
    if episode_id is None:
        return "No episode id provided", 400
    ds = Datastore()
    try:
        episode = ds.get_episode(episode_id)
    except EpisodeNotFound:
        return "Episode not found", 404
    return f"<audio controls autoplay src='{episode.assets.download_link}'>"


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
