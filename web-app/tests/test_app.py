import os

os.environ["MONGO_URI"] = "mongodb://localhost:27017"

import pytest
from bson import ObjectId
import app as app_module


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture
def mock_db(monkeypatch):
    users = []

    class FakeUsers:
        def find_one(self, query):
            # lookup by email
            if "email" in query:
                for user in users:
                    if user["email"] == query["email"]:
                        return user

            # lookup by _id
            if "_id" in query:
                for user in users:
                    if user["_id"] == query["_id"]:
                        return user

            return None

        def insert_one(self, doc):
            if "_id" not in doc:
                doc["_id"] = ObjectId()
            users.append(doc)

        def update_one(self, query, update):
            for user in users:
                if user["_id"] == query.get("_id"):
                    user.update(update.get("$set", {}))

    class FakeDB:
        users = FakeUsers()

    monkeypatch.setattr(app_module, "db", FakeDB())
    return users


def test_login_page(client):
    res = client.get("/login")
    assert res.status_code == 200


def test_signup_page(client):
    res = client.get("/signup")
    assert res.status_code == 200


def test_signup_inserts_user(client, mock_db):
    res = client.post(
        "/signup", data={"email": "subject1@tests.com", "password": "pass123"}
    )

    assert res.status_code == 302
    assert len(mock_db) == 1
    assert mock_db[0]["email"] == "subject1@tests.com"
    assert mock_db[0]["password"] == "pass123"


def test_signup_duplicate_email(client, mock_db):
    client.post("/signup", data={"email": "subject1@tests.com", "password": "pass123"})

    res = client.post(
        "/signup", data={"email": "subject1@tests.com", "password": "pass123"}
    )

    assert res.status_code == 200
    assert b"Email already taken." in res.data
    assert len(mock_db) == 1


def test_login_success_allows_home_access(client, mock_db):
    # add fake user directly to fake DB
    user = {"_id": ObjectId(), "email": "subject1@tests.com", "password": "pass123"}
    mock_db.append(user)

    with client:
        res = client.post(
            "/login", data={"email": "subject1@tests.com", "password": "pass123"}
        )
        assert res.status_code == 302

        home_res = client.get("/")
        assert home_res.status_code == 200


def test_login_failure(client, mock_db):
    user = {"_id": ObjectId(), "email": "subject1@tests.com", "password": "pass123"}
    mock_db.append(user)

    res = client.post(
        "/login", data={"email": "subject1@tests.com", "password": "wrongpass"}
    )

    assert res.status_code == 200
    assert b"Invalid email or password." in res.data


def test_logout_redirects_to_login(client, mock_db):
    user = {"_id": ObjectId(), "email": "subject1@tests.com", "password": "pass123"}
    mock_db.append(user)

    with client:
        client.post(
            "/login", data={"email": "subject1@tests.com", "password": "pass123"}
        )

        res = client.get("/logout")
        assert res.status_code == 302

        # after logout, home should no longer be accessible
        home_res = client.get("/")
        assert home_res.status_code == 302
