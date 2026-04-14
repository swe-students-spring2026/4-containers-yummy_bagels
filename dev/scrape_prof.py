import requests
from bs4 import BeautifulSoup
import json
from pathlib import Path
from urllib.parse import urljoin
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["yummy_bagels"]

BASE_URL = "https://cs.nyu.edu/"


page = requests.get(f"{BASE_URL}/dynamic/people/faculty/type/20/")
soup = BeautifulSoup(page.text,"html.parser")

faculty_list = soup.select("ul.people-listing li")

for li in faculty_list:
    img_tag = li.select_one("img")
    name_tag = li.select_one("p.name.bold a")
    

    if not img_tag or not name_tag:
        continue

    name = name_tag.text.strip()
    img_url = urljoin(BASE_URL, img_tag["src"])

    img_bytes = requests.get(img_url).content
    try:
        db.faculty.update_one(
            {"name": name},
            {"$set": {"name": name, "photo": img_bytes}},
            upsert=True,
            )
        print(f"Added {name}")
    except Exception as e:
        print(f"Skipped {name} - {e}")
    

    

print(f"Done! {db.faculty.count_documents({})} faculty members added.")








