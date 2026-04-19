"""
Tests for the machine learning client
"""

import os
import io
import sys
from unittest.mock import patch
import pandas as pd
from client import convert_to_name, decode_image, dump_faculty_images

# pylint: disable=import-outside-toplevel
# pylint: disable=too-few-public-methods

DB_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "Amos_Bloomberg.jpg")
TEST_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "Amos_Bloomberg_input.jpg")
with open(TEST_IMAGE_PATH, "rb") as f:
    TEST_BYTES = f.read()


class FakeCursor:
    """
    Fake MongoDB Cursor.
    """

    def __init__(self, docs):
        self.docs = list(docs)

    def __iter__(self):
        return iter(self.docs)


class FakeCollection:
    """
    Mock MongoDB Collection.
    """

    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def find(self):
        """
        Return fake cursor of all stored documents.
        """
        return FakeCursor(self.docs)

    def find_one(self):
        """
        Return first stored document or none if collection is empty.
        """
        return self.docs[0] if self.docs else None

    def insert_one(self, doc):
        """
        Append document.
        """
        self.docs.append(doc)


class FakeDB:
    """
    Mock MongoDB Database.
    """

    def __init__(self, data):
        self._collections = {name: FakeCollection(docs) for name, docs in data.items()}

    def __getitem__(self, key):
        if key not in self._collections:
            self._collections[key] = FakeCollection([])
        return self._collections[key]

    def __getattr__(self, key):
        return self[key]


class TestNameFormatting:
    """
    Tests for correct name formatting.
    """

    def test_filename_to_name(self):
        """
        Test converting a filename to a readable name.
        """
        assert convert_to_name("faculty_images/Amos_Bloomberg.jpg") == "Amos Bloomberg"

    def test_middle_name(self):
        """
        Test converting a name to filename.
        """
        assert (
            convert_to_name("faculty_images/Luke_Amos_Sribhud.jpg")
            == "Luke Amos Sribhud"
        )


class TestImageDecoding:
    """
    Tests for image byte handling.
    """

    def test_valid_image(self):
        """
        Test image decoding.
        """
        assert decode_image(TEST_BYTES) is not None

    def test_invalid_image(self):
        """
        Test for invalid image decoding.
        """
        assert decode_image(b"qwerty") is None


class TestFacultyImageDump:
    """
    Tests for pulling faculty images to disk.
    """

    def test_writes_to_disk(self, tmp_path):
        """
        Tests for properly downloading images locally.
        """
        fake_db = FakeDB(
            {
                "faculty": [
                    {"name": "Luke Sribhud", "photo": TEST_BYTES},
                    {"name": "Joe Sribhud", "photo": TEST_BYTES},
                ],
            }
        )
        output_dir = str(tmp_path / "faculty_images")
        dump_faculty_images(fake_db, output_dir)

        assert os.path.exists(os.path.join(output_dir, "Luke_Sribhud.jpg"))
        assert os.path.exists(os.path.join(output_dir, "Joe_Sribhud.jpg"))


class TestEndpoint:
    """
    Tests for /find-lookalike endpoint.
    """

    @classmethod
    def setup_class(cls):
        """
        Load Flask app with Mongo and test environment variables.
        Also clears any cached client import.
        """
        os.environ["MONGO_URI"] = "mongodb://localhost:27017"
        os.environ["MONGO_DBNAME"] = "test_db"

        if "client" in sys.modules:
            del sys.modules["client"]

        with patch("pymongo.MongoClient"), patch("client.dump_faculty_images"):
            import client as client_module

            client_module.app.config["TESTING"] = True
            cls.flask_client = client_module.app.test_client()
            cls.client_module = client_module

    @patch("client.DeepFace.find")
    def test_successfull_request(self, mock_find):
        """
        Tests POST /find-lookalike endpoint, so that a response is successful.
        """
        mock_find.return_value = [
            pd.DataFrame(
                {
                    "identity": [DB_IMAGE_PATH],
                }
            )
        ]
        self.client_module.db = FakeDB(
            {"faculty": [{"name": "Amos Bloomberg", "photo": TEST_BYTES}]}
        )

        response = self.flask_client.post(
            "/find-lookalike",
            data={"img1": (io.BytesIO(TEST_BYTES), "test.jpg")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 200

    @patch("client.DeepFace.find")
    def test_returns_name_and_photo(self, mock_find):
        """
        Tests POST /find-lookalike endpoint, so that a response contains a name and photo.
        """
        mock_find.return_value = [
            pd.DataFrame(
                {
                    "identity": [DB_IMAGE_PATH],
                }
            )
        ]
        self.client_module.db = FakeDB(
            {"faculty": [{"name": "Amos Bloomberg", "photo": TEST_BYTES}]}
        )
        response = self.flask_client.post(
            "/find-lookalike",
            data={"img1": (io.BytesIO(TEST_BYTES), "test.jpg")},
            content_type="multipart/form-data",
        )
        data = response.get_json()
        assert data["name"] == "Amos Bloomberg"
        assert data["photo"] is not None

    def test_unsuccessfull_request(self):
        """
        Tests POST /find-lookalike endpoint, so that the response is unsuccessful.
        """
        response = self.flask_client.post("/find-lookalike")
        assert response.status_code == 400
