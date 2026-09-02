import logging
import secrets
import sqlite3
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import sentry_sdk
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from auth import auth
from auth.auth import hash_password, hash_session_token
from business.entities import User
from business.podcast import Feed, PlayInfo
from business.podcast_service import PodcastService
from business.rss import FeedParserRssParser
from business.user_service import TooManyRegistrations, UserService
from persistence.datastore import (
    Datastore,
    EpisodeNotFound,
    UnknownUser,
    UserAlreadyExists,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class Settings(BaseSettings):
    secret_admission_string: str
    db_connection_string: str = "./db/poddb.db"
    sentry_dsn: str
    sentry_default_pii: bool
    environment: str

    model_config = SettingsConfigDict(env_file=".env", frozen=True, extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def database_connection(
    settings: Settings = Depends(get_settings),
) -> sqlite3.Connection:
    return sqlite3.connect(settings.db_connection_string, check_same_thread=False)


def user_service(
    connection: sqlite3.Connection = Depends(database_connection),
) -> UserService:
    return UserService(datastore=Datastore(connection=connection))


def podcast_service(
    connection: sqlite3.Connection = Depends(database_connection),
) -> PodcastService:
    return PodcastService(
        datastore=Datastore(connection=connection), rss_parser=FeedParserRssParser()
    )


class TooManyRequests(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


class Unauthorized(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail=detail)


class BadRequest(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status.HTTP_400_BAD_REQUEST, detail=detail)


def refresh_all_feeds() -> None:
    podcast_service().update_all_feeds()


scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, FastAPI]:
    settings = get_settings()
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            send_default_pii=settings.sentry_default_pii,
        )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)
origins = ["http://localhost:5173", "https://podcast.simisticot.com"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def authenticated_user(
    response: Response,
    session=Cookie(""),
    service: UserService = Depends(user_service),
) -> User:
    try:
        return service.find_user_by_active_session(
            token=session, current_time=datetime.now(UTC)
        )
    except UnknownUser:
        response.delete_cookie("session")
        raise Unauthorized(detail="invalid session")


class Credentials(BaseModel):
    email: str
    password: str

    @field_validator("email", mode="after")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.lower()


@app.get("/health")
def health() -> str:
    raise Exception("oh no!")
    return "I'm good :)"


class Registration(BaseModel):
    credentials: Credentials
    secret_admission_string: str


@app.post("/register")
def register(
    registration: Registration,
    service: UserService = Depends(user_service),
    settings: Settings = Depends(get_settings),
) -> str:
    if not secrets.compare_digest(
        registration.secret_admission_string, settings.secret_admission_string
    ):
        raise BadRequest(detail="Wrong secret admission string")
    try:
        service.register_user(
            user_email=registration.credentials.email,
            password_hash=hash_password(password=registration.credentials.password),
        )
        return "Welcome :)"
    except UserAlreadyExists:
        raise BadRequest(detail="Email already taken")
    except TooManyRegistrations:
        raise TooManyRequests(
            detail="Too many registrations recently, come back some other day"
        )


@app.post("/login")
def login(
    credentials: Credentials,
    response: Response,
    service: UserService = Depends(user_service),
) -> str:
    try:
        candidate = service.get_login_candidate(credentials.email)
        if candidate.failed_logins > 3:
            raise TooManyRequests(detail="Too many failed attempts, come back later")
        if auth.password_is_valid(
            password=credentials.password, hash=candidate.password_hash
        ):
            # clear existing sessions to avoid having multiple active sessions
            service.delete_all_sessions(user_id=candidate.user.id)

            session_token = secrets.token_urlsafe(32)
            session_token_hash = hash_session_token(session_token)
            service.create_session(
                token_hash=session_token_hash,
                user_id=candidate.user.id,
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
            response.set_cookie(
                key="session",
                value=session_token,
                httponly=True,
                secure=True,
                samesite="lax",
                max_age=30 * 24 * 60 * 60,  # a month
            )
            return "You are now logged in"
        else:
            service.add_failed_login(user_id=candidate.user.id)
            raise BadRequest(detail="Wrong credentials")
    except UnknownUser:
        raise BadRequest(detail="Wrong credentials")


@app.post("/logout")
def logout(
    response: Response,
    user: User = Depends(authenticated_user),
    service: UserService = Depends(user_service),
) -> str:
    service.delete_all_sessions(user_id=user.id)
    response.delete_cookie(key="session")
    return "goodbye"


class PodcastFeed(BaseModel):
    feed_entries: list[PlayInfo]
    next_page: int


@app.get("/me")
def me(
    user: User = Depends(authenticated_user),
) -> User:
    return user


@app.get("/my_feed")
def my_feed(
    page: int = 1,
    search: str = "",
    chronological: bool = False,
    user: User = Depends(authenticated_user),
    service: PodcastService = Depends(podcast_service),
) -> PodcastFeed:
    entries = service.get_user_home_feed(
        user_id=user.id, page=page, search=search, chronological=chronological
    )
    return PodcastFeed(feed_entries=entries, next_page=page + 1)


@app.get("/feed/{feed_id}")
def single_feed(
    feed_id: str,
    page: int = 1,
    user: User = Depends(authenticated_user),
    chronological: bool = False,
    service: PodcastService = Depends(podcast_service),
) -> PodcastFeed:
    entries = service.get_single_feed(
        user_id=user.id, page=page, chronological=chronological, feed_id=feed_id
    )
    return PodcastFeed(feed_entries=entries, next_page=page + 1)


@app.post("/listened/{episode_id}")
def listened(
    episode_id: str,
    seconds_listened: int,
    user: User = Depends(authenticated_user),
    service: PodcastService = Depends(podcast_service),
) -> str:
    try:
        service.get_episode(episode_id, user.id)
    except EpisodeNotFound:
        raise HTTPException(status_code=404, detail="Episode not found")
    service.update_current_play_time(episode_id, user.id, seconds_listened)
    return f"updated playtime to {seconds_listened}"


@app.post("/refresh")
def refresh(
    user: User = Depends(authenticated_user),
    service: PodcastService = Depends(podcast_service),
) -> str:
    service.update_user_feeds(user.id)
    return "Refreshed all your feeds"


@app.post("/subscribe")
def subscribe(
    feed_url: str,
    user: User = Depends(authenticated_user),
    service: PodcastService = Depends(podcast_service),
) -> str:
    service.subscribe_user_to_podcast(user.id, feed_url)
    return "Subscribed Successfully"


class LatestListen(BaseModel):
    play_info: PlayInfo | None


@app.get("/latest")
def latest(
    user: User = Depends(authenticated_user),
    service: PodcastService = Depends(podcast_service),
) -> LatestListen:
    info = service.get_latest_listen_play_info(user.id)
    return LatestListen(play_info=info)


@app.get("/subscribed_feeds")
def subscribed_feeds(
    user: User = Depends(authenticated_user),
    service: PodcastService = Depends(podcast_service),
) -> list[Feed]:
    return service.get_user_subscribed_feeds(user.id)
