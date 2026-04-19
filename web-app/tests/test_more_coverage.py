"""
Tests for the web app.
"""

# pylint: disable=wrong-import-position,too-few-public-methods,redefined-outer-name,protected-access,duplicate-code

import base64
import os
from datetime import datetime
import importlib.util
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
from bson import ObjectId

os.environ["MONGO_URI"] = "mongodb://localhost:27017"
os.environ.setdefault("MONGO_DBNAME", "test_db")
os.environ.setdefault("SECRET_KEY", "dev")

import app as app_module


class _InsertResult:
    """
    Insert Results.
    """

    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class _FakeFind:
    """
    Fake find.
    """

    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, field, direction):
        """
        Sort.
        """
        reverse = direction == -1
        self._docs.sort(key=lambda d: d.get(field), reverse=reverse)
        return self

    def __iter__(self):
        return iter(self._docs)


class _FakeUploadHistory:
    """
    Fake upload history.
    """

    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        """
        Insert one id.
        """
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        self.docs.append(doc)
        return _InsertResult(doc["_id"])

    def find_one(self, query):
        """
        Find one.
        """
        for doc in self.docs:
            ok = True
            for key, value in query.items():
                if doc.get(key) != value:
                    ok = False
                    break
            if ok:
                return doc
        return None

    def find(self, query):
        """
        Finds.
        """
        filtered = []
        for doc in self.docs:
            ok = True
            for key, value in query.items():
                if doc.get(key) != value:
                    ok = False
                    break
            if ok:
                filtered.append(doc)
        return _FakeFind(filtered)


@pytest.fixture
def client():
    """
    Client def.
    """
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


@pytest.fixture
def fake_db(monkeypatch):
    """
    Fake db. Returns fake users, images, and history.
    """
    users = []
    images = []
    upload_history_collection = _FakeUploadHistory()

    class FakeUsers:
        """
        Fake users.
        """

        def find_one(self, query):
            """
            Finds one.
            """
            if "email" in query:
                for user in users:
                    if user["email"] == query["email"]:
                        return user
            if "_id" in query:
                for user in users:
                    if user["_id"] == query["_id"]:
                        return user
            return None

        def insert_one(self, doc):
            """
            Inserts one.
            """
            if "_id" not in doc:
                doc["_id"] = ObjectId()
            users.append(doc)

        def update_one(self, query, update):
            """
            Updates one.
            """
            for user in users:
                if user["_id"] == query.get("_id"):
                    user.update(update.get("$set", {}))

    class FakeImages:
        """
        Fake images.
        """

        def insert_one(self, doc):
            """
            Inserts one image.
            """
            images.append(doc)

    class FakeFaculty:
        """
        Fake faculty.
        """

        def __init__(self):
            self._docs = []

        def find_one(self, query):
            """
            Finds one.
            """
            for doc in self._docs:
                if doc.get("name") == query.get("name"):
                    return doc
            return None

    class FakeDB:
        """
        Fake db.
        """

        users = FakeUsers()
        images = FakeImages()
        faculty = FakeFaculty()
        upload_history = upload_history_collection

    monkeypatch.setattr(app_module, "db", FakeDB())
    monkeypatch.setattr(
        app_module, "upload_history_collection", upload_history_collection
    )
    return {
        "users": users,
        "images": images,
        "upload_history": upload_history_collection,
    }


def _create_and_login(client, fake_db, email="user@example.com", password="pass123"):
    """
    Creates fake db user and logs in. Returns email, pw
    """
    fake_db["users"].append({"_id": ObjectId(), "email": email, "password": password})
    with client:
        res = client.post("/login", data={"email": email, "password": password})
        assert res.status_code == 302
    return email, password


def test_import_requires_mongo_uri():
    """
    Tests import requiring mongoURI.
    """
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    old_mongo_uri = os.environ.pop("MONGO_URI", None)
    try:
        spec = importlib.util.spec_from_file_location("app_no_env", app_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        try:
            with patch("dotenv.load_dotenv", return_value=False):
                spec.loader.exec_module(module)
            assert False, "Expected RuntimeError due to missing MONGO_URI"
        except RuntimeError as exc:
            assert "MONGO_URI must be set" in str(exc)
    finally:
        if old_mongo_uri is not None:
            os.environ["MONGO_URI"] = old_mongo_uri


def test_helper_functions():
    """
    Tests all helper functions.
    """
    assert app_module.allowed_file("photo.jpg") is True
    assert app_module.allowed_file("photo.gif") is False

    bad_name, bad_bytes, bad_mime, err = app_module.decode_camera_image("no-comma")
    assert bad_name is None and bad_bytes is None and bad_mime is None
    assert "invalid" in err.lower()

    data_url = "data:image/png;base64," + base64.b64encode(b"abc").decode("ascii")
    name, image_bytes, mime_type, err = app_module.decode_camera_image(data_url)
    assert err is None
    assert name.endswith(".png")
    assert image_bytes == b"abc"
    assert mime_type == "image/png"

    assert app_module.guess_extension("image/jpeg") in {".jpg", ".jpeg", ".jpe"}
    assert app_module.guess_extension("image/jpeg", original_name="x.jpe") == ".jpe"
    assert (
        app_module.guess_extension("application/octet-stream", original_name="x")
        == ".bin"
    )

    assert app_module._object_id("not-an-oid") is None
    oid = ObjectId()
    assert app_module._object_id(str(oid)) == oid


def test_home_post_without_image_shows_error(client, fake_db):
    """
    Tests if user posts without uploading an image.
    """
    _create_and_login(client, fake_db)
    res = client.post("/", data={})
    assert res.status_code == 200
    assert b"Please choose an image file or take a photo" in res.data


def test_home_post_disallowed_extension(client, fake_db):
    """
    Tests if user posts unsupported extension types. (not possible)
    """
    _create_and_login(client, fake_db)
    res = client.post(
        "/",
        data={"image": (BytesIO(b"fake"), "bad.gif")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert b"Only PNG, JPG, and JPEG files are allowed" in res.data


def test_home_post_ml_success_with_photo(client, fake_db, monkeypatch):
    """
    Tests post to ML.
    """
    _create_and_login(client, fake_db)

    class _Resp:
        """
        Response class.
        """

        status_code = 200

        @staticmethod
        def json():
            """
            Returns success json.
            """
            return {
                "name": "Prof X",
                "photo": "00ff",
                "matched_photo_mime": "image/jpeg",
            }

    monkeypatch.setattr(app_module.requests, "post", lambda *args, **kwargs: _Resp())

    res = client.post(
        "/",
        data={"image": (BytesIO(b"\xff\xd8\xff"), "selfie.jpg")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert b"Best match: Prof X" in res.data
    assert len(fake_db["images"]) == 1
    assert len(fake_db["upload_history"].docs) == 1


def test_home_post_ml_error_json(client, fake_db, monkeypatch):
    """
    Test json error.
    """
    _create_and_login(client, fake_db)

    class _Resp:
        status_code = 500
        text = "boom"

        @staticmethod
        def json():
            """
            Return ML service error JSON.
            """
            return {"error": "bad things"}

    monkeypatch.setattr(app_module.requests, "post", lambda *args, **kwargs: _Resp())

    res = client.post(
        "/",
        data={"image": (BytesIO(b"\xff\xd8\xff"), "selfie.jpg")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert b"ML service error: 500 - bad things" in res.data


def test_home_post_ml_error_text(client, fake_db, monkeypatch):
    """
    Test error text.
    """
    _create_and_login(client, fake_db)

    class _Resp:
        """
        Response class.
        """

        status_code = 500
        text = "plain error"

        @staticmethod
        def json():
            """
            Does not return json.
            """
            raise ValueError("not json")

    monkeypatch.setattr(app_module.requests, "post", lambda *args, **kwargs: _Resp())

    res = client.post(
        "/",
        data={"image": (BytesIO(b"\xff\xd8\xff"), "selfie.jpg")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert b"ML service error: 500 - plain error" in res.data


def test_home_post_ml_connection_error(client, fake_db, monkeypatch):
    """
    Tests connectoin issue error.
    """
    _create_and_login(client, fake_db)

    def _raise(*_args, **_kwargs):
        """
        Connection offline.
        """
        raise requests.RequestException("offline")

    monkeypatch.setattr(app_module.requests, "post", _raise)

    res = client.post(
        "/",
        data={"image": (BytesIO(b"\xff\xd8\xff"), "selfie.jpg")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert b"Could not connect to ML service:" in res.data


def test_dashboard_post_no_changes(client, fake_db):
    """
    Tests dashboard post no changes.
    """
    _create_and_login(client, fake_db, password="samepass")
    res = client.post("/dashboard", data={"password": "samepass"})
    assert res.status_code == 200
    assert b"No changes were made." in res.data


def test_dashboard_post_updates_password(client, fake_db):
    """
    Tests updated password.
    """
    email, _ = _create_and_login(client, fake_db, password="oldpass")
    res = client.post("/dashboard", data={"password": "newpass"})
    assert res.status_code == 200
    assert b"Profile updated successfully." in res.data
    assert fake_db["users"][0]["email"] == email
    assert fake_db["users"][0]["password"] == "newpass"


def test_history_image_route(client, fake_db):
    """
    Tests history image route.
    """
    _create_and_login(client, fake_db)
    with client:
        # create a history record for the logged in user
        current_user_id = fake_db["users"][0]["_id"]
        user_email = fake_db["users"][0]["email"]
        entry_id = ObjectId()
        fake_db["upload_history"].docs.append(
            {
                "_id": entry_id,
                "user_id": current_user_id,
                "uploaded_photo": b"up",
                "uploaded_content_type": "image/jpeg",
                "matched_photo": b"mp",
                "matched_content_type": "image/jpeg",
                "created_at": datetime.now(),
                "user_email": user_email,
                "original_filename": "selfie.jpg",
                "timestamp": "t",
            }
        )

        assert client.get(f"/history/image/{entry_id}/badkind").status_code == 404
        assert client.get("/history/image/not-an-oid/uploaded").status_code == 404

        uploaded = client.get(f"/history/image/{entry_id}/uploaded")
        assert uploaded.status_code == 200
        assert uploaded.data == b"up"

        matched = client.get(f"/history/image/{entry_id}/matched")
        assert matched.status_code == 200
        assert matched.data == b"mp"


def test_save_and_load_history_entry_helpers(client, fake_db):
    """
    Tests saving and loading history helper functions.
    """
    _create_and_login(client, fake_db)

    with app_module.app.test_request_context("/"):
        # ensure login state in this request context
        app_module.login_user(app_module.User(fake_db["users"][0]))

        record = app_module.save_history_entry(
            user_email="user@example.com",
            original_name="selfie.jpg",
            uploaded_mime="image/jpeg",
            uploaded_bytes=b"up",
            ml_data={"name": "Prof X", "photo": "not-hex"},
        )
        assert record["match_result"]["matched_image_url"] is None

        entries = app_module.load_user_history("user@example.com")
        assert len(entries) == 1
        assert entries[0]["original_filename"] == "selfie.jpg"
