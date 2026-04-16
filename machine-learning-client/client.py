"""
Machine Learning Client
"""

# pylint: disable=no-member

import re
import unicodedata
import os
import cv2
from deepface import DeepFace
from flask import Flask, request
import numpy as np
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

mongo_uri = os.getenv("MONGO_URI")
mongo_dbname = os.getenv("MONGO_DBNAME", "yummy_bagels")
if not mongo_uri:
    raise RuntimeError("MONGO_URI must be set in .env to connect to MongoDB.")
client = MongoClient(
    mongo_uri,
    serverSelectionTimeoutMS=3000,
    connectTimeoutMS=3000,
    socketTimeoutMS=5000,
)
db = client[mongo_dbname]


def safe_filename(name):
    """helper function to use only unicode for filenames"""
    normalized = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    )
    normalized = normalized.replace(" ", "_")
    normalized = re.sub(r"[^A-Za-z0-9_-]", "", normalized)
    return normalized + ".jpg"


def dump_faculty_images(database, output_dir):
    """
    Pull faculty photos from database and write to disk.
    """
    os.makedirs(output_dir, exist_ok=True)
    for member in database.faculty.find():
        filename = member["name"].replace(" ", "_") + ".jpg"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "wb") as f:
            f.write(member["photo"])


def convert_to_name(filepath):
    """
    Convert a faculty image path to a readable name.
    """
    return os.path.basename(filepath).replace("_", " ").replace(".jpg", "")


def decode_image(file_bytes):
    """
    Decode image bytes into a numpy array.
    """
    return cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)


def find_lookalike(img):
    """
    Run Deepface similarity search
    """
    results = DeepFace.find(
        img_path=img,
        db_path="faculty_images/",
        similarity_search=True,
        k=3,
    )
    return results


dump_faculty_images(db, "faculty_images")


@app.post("/find-lookalike")
def find():
    """
    Take image from user and compare it to NYU Courant faculty
    """
    if "img1" not in request.files:
        return {"error": "No image provided"}, 400

    file_bytes = request.files["img1"].read()
    input_img = decode_image(file_bytes)
    results = find_lookalike(input_img)

    results = DeepFace.find(
        img_path=input_img,
        db_path="faculty_images/",
        # similarity_search=True,
        # k=3,
        silent=True,
        enforce_detection=False,
    )

    if not results or results[0].empty:
        return "No match found", 404

    top_match = results[0].iloc[0]
    matched_name = convert_to_name(top_match["identity"])

    with open(top_match["identity"], "rb") as f:
        picture_bytes = f.read()

    # distance = top_match["distance"]
    print(matched_name)
    return {
        "name": matched_name,
        "photo": picture_bytes.hex(),
    }


if __name__ == "__main__":
    app.run(debug=True, port=5001, host="0.0.0.0")
