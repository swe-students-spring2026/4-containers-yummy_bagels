"""
Machine Learning Client
"""
# pylint: disable=no-member

import os
import cv2
from deepface import DeepFace
from flask import Flask, request
import numpy as np
from pymongo import MongoClient


app = Flask(__name__)

client = MongoClient("mongodb://mongodb:27017")
db = client["yummy_bagels"]

os.makedirs("faculty_images",exist_ok=True)
for member in db.faculty.find():
    filename = member["name"].replace(" ", "_") + ".jpg"
    filepath = os.path.join("faculty_images", filename)
    with open(filepath, "wb") as f:
        f.write(member["photo"])

@app.post("/find-lookalike")
def find():
    """
    Take image from user and compare it to NYU Courant faculty
    """
    file_bytes_1 = request.files["img1"].read()

    input_img = cv2.imdecode(np.frombuffer(file_bytes_1, np.uint8), cv2.IMREAD_COLOR)

    results = DeepFace.find(img_path = input_img,
                            db_path="faculty_images/",
                            similarity_search=True,
                            k=3,)

    top_match = results[0].iloc[0]

    matched_name = os.path.basename(top_match["identity"]).replace("_", " ").replace(".jpg", "")
    #distance = top_match["distance"]

    return matched_name

if __name__ == "__main__":
    app.run(debug=True, port=5001)
