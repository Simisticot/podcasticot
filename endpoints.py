from functools import lru_cache

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.jwks_client import PyJWKClient
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from business.podcast import PlayInfo
from business.podcast_service import PodcastService
from business.rss import FeedParserRssParser
from persistence.datastore import Datastore


class Settings(BaseSettings):
    auth0_domain: str
    auth0_audience: str
    auth0_issuer: str
    auth0_algorithms: str

    class Config:
        env_file = ".podcasticotapi.env"
        frozen = True


@lru_cache
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


app = FastAPI()
origins = ["http://localhost:5173"]

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


class Message(BaseModel):
    content: str


@app.get("/")
def test() -> Message:
    return Message(content="coucou smile")


class User(BaseModel):
    email: str


@app.get("/whoami")
def whoami(user_email=Depends(authenticated_user_email)) -> User:
    return User(email=user_email)


class HomeFeed(BaseModel):
    entries: list[PlayInfo]


@app.get("/my_feed")
def my_feed(
    user_email=Depends(authenticated_user_email),
    service: PodcastService = Depends(podcast_service),
) -> HomeFeed:
    user = service.find_user_by_email(user_email)
    feed = service.get_user_home_feed(user_id=user.id, page=0)
    return HomeFeed(entries=feed)
