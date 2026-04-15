"""NYU Courant Faculty Scraper"""

# pylint: disable=R0801

import os
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

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

# Skip if already seeded to avoid duplicates
if db.faculty.count_documents({}) > 0:
    print("Faculty collection already has data. Skipping seed.")
    raise SystemExit(0)

BASE_URL = "https://cs.nyu.edu/"

page = requests.get(f"{BASE_URL}/dynamic/people/faculty/type/20/", timeout=(5, 10))
soup = BeautifulSoup(page.text, "html.parser")

faculty_list = soup.select("ul.people-listing li")

for li in faculty_list:
    img_tag = li.select_one("img")
    name_tag = li.select_one("p.name.bold a")

    if not img_tag or not name_tag:
        continue

    name = name_tag.text.strip()
    img_url = urljoin(BASE_URL, img_tag["src"])

    img_bytes = requests.get(img_url, timeout=(5, 10)).content
    try:
        db.faculty.update_one(
            {"name": name},
            {"$set": {"name": name, "photo": img_bytes}},
            upsert=True,
        )
        print(f"Added {name}")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Skipped {name} - {e}")

print(f"Done! {db.faculty.count_documents({})} faculty members added.")
