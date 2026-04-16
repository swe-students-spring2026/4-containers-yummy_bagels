"""
Tests for the machine learning client
"""
import app as app_module
import os
import pytest
import coverage
import unittest



TEST_IMAGE_PATH = os.path.join(os.path.dirname(__file__),"Amos_Bloomberg.jpg")
with open(TEST_IMAGE_PATH, "rb") as f:
    TEST_BYTES = f.read()

class FakeCursor:
    """
    Fake MongoDB Cursor
    """
    def __init__(self,docs):
        self.docs = list(docs)

    def __iter__(self):
        return iter(self.docs)

class FakeCollection:
    """
    Mock MongoDB Collection
    """
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def find(self,query=None):
        return FakeCursor(self.docs)
    
    def find_one(self, query=None):
        return self.docs[0] if self.docs else None
    
    def insert_one(self,doc):
        self.docs.append(doc)

class FakeDB:
    """
    Mock MongoDB Database
    """
    def __init__(self,data):
        self.collections = {name: FakeCollection(docs) for name, docs in data.items()}

    def __getitem__(self,key):
        if key not in self._collections:
            self._colelctions[key] = FakeCollection([])
        return self._collections[key]

class TestNameFormatting:
    """
    Tests for correct name formatting.
    """
    def test_filename_to_name(self):
        path = "faculty_images/Amos_Bloomberg.jpg"
        name = os.path.basename(path.replace("_", " ").replace(".jpg", ""))
        assert name == "Amos Bloomberg"

    def test_middle_name(self):
        path = "faculty_images/Luke_Amos_Sribhud.jpg"
        name = os.path.basename(path.replace("_", " ").replace(".jpg", ""))
        assert name == "Luke Amos Bloomberg"
    
    def test_name_to_filename(self):
        filename = "Luke Amos Sribhud".replace(" ","_") + ".jpg"
        assert filename == "Luke_Amos_Sribhud"

class TestImageImageDecoding:
    """
    Tests for correct image byte handling.
    """
    def test_decode_image(self, path):
        filepath = path / "Amos_Bloomberg.jpg"
        with open(filepath,"wb") as f:
            f.write(TEST_BYTES)
        assert filepath.exists()
        assert filepath.stat().st_size > 0
    
    def test_directory_created(self, path):
        img_dir = path / "faculty_images"
        os.makedirs(img_dir, exist_ok=True)
        assert img_dir.exists()





class TestClient(unittest.TestCase):
    def setUp(self):
        fake_db = FakeDB({
            "faculty": [
                {
                    {"name": "Amos Bloomberg", "photo": TEST_BYTES},
                }
            ],
        })




