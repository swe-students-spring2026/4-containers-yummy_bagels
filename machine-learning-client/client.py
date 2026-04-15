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


os.makedirs("faculty_images", exist_ok=True)
for member in db.faculty.find():
    filename = safe_filename(member["name"])
    filepath = os.path.join("faculty_images", filename)
    with open(filepath, "wb") as f:
        f.write(member["photo"])


@app.post("/find-lookalike")
def find():
    """
    Take image from user and compare it to NYU Courant faculty
    """
    uploaded_file = request.files.get("img1")
    if not uploaded_file:
        return "No file uploaded", 400

    file_bytes_1 = uploaded_file.read()
    input_img = cv2.imdecode(np.frombuffer(file_bytes_1, np.uint8), cv2.IMREAD_COLOR)

    if input_img is None:
        return "Invalid image file", 400

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
    matched_name = (
        os.path.basename(top_match["identity"]).replace("_", " ").replace(".jpg", "")
    )
    # distance = top_match["distance"]
    return matched_name, 200


if __name__ == "__main__":
    app.run(debug=True, port=5001, host="0.0.0.0")
