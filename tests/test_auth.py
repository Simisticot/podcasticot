import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest
from _pytest.fixtures import fixture
from fastapi.testclient import TestClient

from business.user_service import UserService
from endpoints import app, get_settings
from persistence.datastore import UnknownUser
from persistence.migration import migrate


@fixture
def test_client(db_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DB_CONNECTION_STRING", str(db_path))
    monkeypatch.setenv("SECRET_ADMISSION_STRING", "titi")

    # clear the lru cache on get_settings otherwise the first connection string is cached for the full test run
    get_settings.cache_clear()

    connection = sqlite3.connect(db_path)
    migrate(conn=connection)
    connection.close()
    return TestClient(app=app, base_url="https://testserver")


def test_unauthenticated_requests_are_rejected(test_client: TestClient) -> None:
    response = test_client.get("/my_feed")
    assert response.status_code == 401


def test_cannot_register_same_user_twice(test_client: TestClient) -> None:
    register_response = test_client.post(
        "/register",
        json={
            "credentials": {"email": "alice@example.com", "password": "toto"},
            "secret_admission_string": "titi",
        },
    )
    assert register_response.status_code == 200
    second_register_response = test_client.post(
        "/register",
        json={
            "credentials": {"email": "alice@example.com", "password": "toto"},
            "secret_admission_string": "titi",
        },
    )
    assert second_register_response.status_code == 400


def test_register_account_and_login(test_client: TestClient) -> None:
    register_response = test_client.post(
        "/register",
        json={
            "credentials": {"email": "alice@example.com", "password": "toto"},
            "secret_admission_string": "titi",
        },
    )
    assert register_response.status_code == 200

    # wrong password fails login
    bad_login_response = test_client.post(
        "/login",
        json={"email": "alice@example.com", "password": "tata"},
    )
    assert bad_login_response.status_code == 400
    assert bad_login_response.cookies.get("session") is None, (
        "there should be no session cookie after an unsuccessful login"
    )

    login_response = test_client.post(
        "/login",
        json={"email": "alice@example.com", "password": "toto"},
    )
    assert login_response.status_code == 200
    assert login_response.cookies.get("session") is not None, (
        "A successful login request should add a session cookie"
    )


def test_set_password_revokes_sessions(
    test_client: TestClient, user_service: UserService
) -> None:
    register_response = test_client.post(
        "/register",
        json={
            "credentials": {"email": "alice@example.com", "password": "toto"},
            "secret_admission_string": "titi",
        },
    )
    assert register_response.status_code == 200

    login_response = test_client.post(
        "/login", json={"email": "alice@example.com", "password": "toto"}
    )
    assert login_response.status_code == 200

    # set password to tata
    user_service.set_user_password(user_email="alice@example.com", new_password="tata")

    me_response = test_client.get("/me")
    assert me_response.status_code == 401, "session should be reset by set password"


def test_set_password_sets_password(
    test_client: TestClient, user_service: UserService
) -> None:
    register_response = test_client.post(
        "/register",
        json={
            "credentials": {"email": "alice@example.com", "password": "toto"},
            "secret_admission_string": "titi",
        },
    )
    assert register_response.status_code == 200

    # password not set to this yet
    bad_login_response = test_client.post(
        "/login", json={"email": "alice@example.com", "password": "tata"}
    )
    assert bad_login_response.status_code == 400
    assert bad_login_response.cookies.get("session") is None, (
        "the password has not yet been set to tata"
    )

    # set password to tata
    user_service.set_user_password(user_email="alice@example.com", new_password="tata")

    login_response = test_client.post(
        "/login", json={"email": "alice@example.com", "password": "tata"}
    )
    assert login_response.status_code == 200, (
        "the password has been set to tata we should be able to log in"
    )

    assert login_response.cookies.get("session") is not None, (
        "the password has been set to tata we should be able to log in"
    )


def test_logout_deletes_session(
    test_client: TestClient, user_service: UserService
) -> None:
    register_response = test_client.post(
        "/register",
        json={
            "credentials": {"email": "alice@example.com", "password": "toto"},
            "secret_admission_string": "titi",
        },
    )
    assert register_response.status_code == 200
    login_response = test_client.post(
        "/login", json={"email": "alice@example.com", "password": "toto"}
    )
    assert login_response.status_code == 200
    token = login_response.cookies["session"]

    logout_response = test_client.post("/logout")
    assert logout_response.status_code == 200

    with pytest.raises(UnknownUser):
        user_service.find_user_by_active_session(
            token=token, current_time=datetime.now(timezone.utc)
        )


def test_11th_registration_within_an_hour_fails(test_client: TestClient) -> None:
    for i in range(11):
        register_response = test_client.post(
            "/register",
            json={
                "credentials": {"email": f"alice{i}@example.com", "password": "toto"},
                "secret_admission_string": "titi",
            },
        )
        assert register_response.status_code == 200

    excess_registration_response = test_client.post(
        "/register",
        json={
            "credentials": {"email": "alice11@example.com", "password": "toto"},
            "secret_admission_string": "titi",
        },
    )
    assert excess_registration_response.status_code == 429, (
        "11th registration should get rate limited"
    )


def test_4th_login_attempt_within_an_hour_fails(test_client: TestClient) -> None:
    register_response = test_client.post(
        "/register",
        json={
            "credentials": {"email": "alice@example.com", "password": "toto"},
            "secret_admission_string": "titi",
        },
    )
    assert register_response.status_code == 200

    for _ in range(4):
        login_response = test_client.post(
            "/login",
            json={"email": "alice@example.com", "password": "tata"},
        )
        assert login_response.status_code == 400

    login_response = test_client.post(
        "/login",
        json={"email": "alice@example.com", "password": "tata"},
    )
    assert login_response.status_code == 429, (
        "4th login attempty should get rate limited"
    )
