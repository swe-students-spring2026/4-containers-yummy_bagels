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
        filename = safe_filename(member["name"])
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


@app.post("/find-lookalike")
def find():
    """
    Take image from user and compare it to NYU Courant faculty,
    Returns top match plus similarity metadata.
    """
    if "img1" not in request.files:
        return {"error": "No image provided"}, 400

    file_bytes = request.files["img1"].read()
    input_img = decode_image(file_bytes)

    if input_img is None:
        return "Invalid image file", 400

    model_name = "VGG-Face"
    distance_metric = "cosine"

    results = DeepFace.find(
        img_path=input_img,
        db_path="faculty_images/",
        model_name=model_name,
        distance_metric=distance_metric,
        # similarity_search=True,
        # k=3,
        silent=True,
        enforce_detection=False,
    )

    if not results or results[0].empty:
        return {"error": "No match found"}, 404

    top_match = results[0].iloc[0]
    matched_path = top_match["identity"]
    matched_name = convert_to_name(matched_path)

    with open(top_match["identity"], "rb") as f:
        picture_bytes = f.read()

    distance = float(top_match["distance"]) if "distance" in top_match else None
    threshold = float(top_match["threshold"]) if "threshold" in top_match else None
    confidence = float(top_match["confidence"]) if "confidence" in top_match else None

    # derived score: higher = more similar
    similarity_score = None
    if distance is not None and threshold not in (None, 0):
        similarity_score = max(0.0, min(100.0, (1 - distance / threshold) * 100))

    return {
        "name": matched_name,
        "photo": picture_bytes.hex(),
        "matched_photo_mime": "image/jpeg",
        "model": model_name,
        "distance_metric": distance_metric,
        "distance": distance,
        "threshold": threshold,
        "confidence": confidence,
        "similarity_score": similarity_score,
        "is_match": distance is not None
        and threshold is not None
        and distance <= threshold,
        "source_face_box": {
            "x": int(top_match["source_x"]) if "source_x" in top_match else None,
            "y": int(top_match["source_y"]) if "source_y" in top_match else None,
            "w": int(top_match["source_w"]) if "source_w" in top_match else None,
            "h": int(top_match["source_h"]) if "source_h" in top_match else None,
        },
        "target_face_box": {
            "x": int(top_match["target_x"]) if "target_x" in top_match else None,
            "y": int(top_match["target_y"]) if "target_y" in top_match else None,
            "w": int(top_match["target_w"]) if "target_w" in top_match else None,
            "h": int(top_match["target_h"]) if "target_h" in top_match else None,
        },
    }


if __name__ == "__main__":
    dump_faculty_images(db, "faculty_images")
    app.run(debug=True, port=5001, host="0.0.0.0")
