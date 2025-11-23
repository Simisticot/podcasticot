from contextlib import asynccontextmanager
from functools import lru_cache
from typing import AsyncGenerator

import jwt
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.jwks_client import PyJWKClient
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from business.entities import User
from business.podcast import PlayInfo
from business.podcast_service import PodcastService
from business.rss import FeedParserRssParser
from persistence.datastore import Datastore, EpisodeNotFound, UnknownUser


class Settings(BaseSettings):
    auth0_domain: str
    auth0_audience: str
    auth0_issuer: str
    auth0_algorithms: str

    class Config:
        env_file = ".podcasticotapi.env"
        frozen = True


def podcast_service() -> PodcastService:
    return PodcastService(
        datastore=Datastore(db_string="./db/poddb.db"), rss_parser=FeedParserRssParser()
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_jwks_client(settings=Depends(get_settings)) -> PyJWKClient:
    jwks_url = f"https://{settings.auth0_domain}/.well-known/jwks.json"
    return jwt.PyJWKClient(jwks_url)


class UnauthorizedException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status.HTTP_403_FORBIDDEN, detail=detail)


scheduler = BackgroundScheduler()


def refresh_all_feeds() -> None:
    podcast_service().update_all_feeds()


scheduler.add_job(func=refresh_all_feeds, trigger="interval", minutes=10)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, FastAPI]:
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

token_auth = HTTPBearer(auto_error=True)


def authenticated_user_email(
    creds: HTTPAuthorizationCredentials | None = Depends(token_auth),
    jwks_client: PyJWKClient = Depends(get_jwks_client),
    settings: Settings = Depends(get_settings),
) -> str:
    assert creds is not None
    assert isinstance(creds.credentials, str)
    signing_key = jwks_client.get_signing_key_from_jwt(creds.credentials).key
    try:
        payload = jwt.decode(
            creds.credentials,
            signing_key,
            algorithms=[settings.auth0_algorithms],
            audience=settings.auth0_audience,
            issuer=settings.auth0_issuer,
        )
    except Exception as error:
        raise UnauthorizedException(detail=str(error))

    return payload["podcasticot/email"]


def authenticated_user(
    user_email: str = Depends(authenticated_user_email),
    service: PodcastService = Depends(podcast_service),
) -> User:
    try:
        return service.find_user_by_email(user_email)
    except UnknownUser:
        return service.save_user(user_email)


class HomeFeed(BaseModel):
    feed_entries: list[PlayInfo]
    next_page: int


@app.get("/my_feed")
def my_feed(
    page: int = 1,
    search: str = "",
    user: User = Depends(authenticated_user),
    service: PodcastService = Depends(podcast_service),
) -> HomeFeed:
    feed = service.get_user_home_feed(user_id=user.id, page=page, search=search)
    return HomeFeed(feed_entries=feed, next_page=page + 1)


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
