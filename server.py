import json
from os import environ as env
from urllib.parse import quote_plus, urlencode
from uuid import uuid4

from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, redirect, render_template, session, url_for, Request, request

from datastore import Datastore
from rss import assets_from_feed_list_chronological

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


# Controllers API
@app.route("/")
def home():
    return render_template(
        "home.html",
        session=session.get("user"),
        pretty=json.dumps(session.get("user"), indent=4),
    )


@app.route("/podhome")
def podhome():
    user_email = session.get("user")["userinfo"]["email"]
    if user_email is None:
        return redirect(url_for("login"))
    ds = Datastore()
    user = ds.find_user(user_email)
    if user is None:
        user = ds.save_user(id=str(uuid4()), email=user_email)
    subscriptions = ds.find_subscriptions(user_id=user.id)
    return render_template(
        template_name_or_list="podcast_home.html",
        episode_asset_list=assets_from_feed_list_chronological([sub.feed_url for sub in subscriptions]),
    )


@app.route("/fetch-feeds", methods=["GET", "POST"])
def fetch_feeds():
    feed_list = request.form["feed_list"].split("\n")
    ds = Datastore()
    user_email = session.get("user")["userinfo"]["email"]
    user = ds.find_user(user_email)
    if user is None:
        user = ds.save_user(id=str(uuid4()), email=user_email)
    for feed in feed_list:
        ds.subscribe(user_id=user.id, feed_url=feed)
    subscriptions = ds.find_subscriptions(user_id=user.id)
    all_feed_assets = assets_from_feed_list_chronological([sub.feed_url for sub in subscriptions])
    return render_template(
        template_name_or_list="feed.html", episode_asset_list=all_feed_assets
    )


@app.post("/play-episode")
def play_episode():
    episode_url = request.form.get("episode_url", None)
    if episode_url is None:
        return "No episode url provided", 400
    return f"<audio controls autoplay src='{episode_url}'>"


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
