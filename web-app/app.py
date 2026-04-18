"""Web app for the project"""

import base64
import mimetypes
import binascii
from io import BytesIO
import json
import os
from pathlib import Path
from datetime import datetime
import requests
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    Response,
    abort,
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from pymongo import MongoClient

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev")

# config for image uplaoding
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:5001/find-lookalike")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg"}
# config for app paths
BASE_DIR = Path(__file__).resolve().parent

# MongoDB connection
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
upload_history_collection = db.upload_history

# Flask login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # redirect here if not logged in


class User(UserMixin):
    """Represents a user for Flask-Login integration."""

    def __init__(self, user):
        self.id = user["_id"]
        self.email = user["email"]
        self.password = user["password"]


@login_manager.user_loader
def load_user(user_id):
    """Load a user from the database by their user ID for Flask-Login integration."""
    # session stores user's _id; load user by _id
    try:
        oid = ObjectId(user_id) if isinstance(user_id, str) else user_id
        user = db.users.find_one({"_id": oid})
        if user:
            return User(user)
    except (InvalidId, ValueError):
        pass
    return None


def allowed_file(filename):
    """Returns true if the image extension is allowed (png, jpg, jpeg)"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def decode_camera_image(data_url):
    """Decode a base64 camera image posted from the homepage."""
    try:
        header, encoded = data_url.split(",", 1)
    except ValueError:
        return None, None, None, "Camera image data was invalid"

    if not header.startswith("data:image/"):
        return None, None, None, "Camera image data was invalid"

    mime_type = header[5:].split(";", 1)[0]
    if mime_type not in ALLOWED_MIME_TYPES:
        return None, None, None, "Only PNG, JPG, and JPEG files are allowed"

    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None, None, None, "Camera image data was invalid"

    extension = "png" if mime_type == "image/png" else "jpg"
    return f"camera-capture.{extension}", image_bytes, mime_type, None


def extract_uploaded_image():
    """Accept either a file upload or a homepage camera capture."""
    uploaded_file = request.files.get("image")
    if uploaded_file and uploaded_file.filename:
        if not allowed_file(uploaded_file.filename):
            return None, None, None, "Only PNG, JPG, and JPEG files are allowed"

        image_bytes = uploaded_file.read()
        if not image_bytes:
            return None, None, None, "Uploaded image was empty"

        return (
            secure_filename(uploaded_file.filename),
            image_bytes,
            uploaded_file.mimetype or "image/jpeg",
            None,
        )

    camera_image_data = request.form.get("camera_image_data", "").strip()
    if camera_image_data:
        return decode_camera_image(camera_image_data)

    return None, None, None, "Please choose an image file or take a photo"


@app.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login via GET and POST requests."""
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")

        # check the database
        user = db.users.find_one({"email": email})
        if user and user["password"] == password:
            login_user(User(user))
            return redirect(url_for("home"))

        return render_template("login.html", error="Invalid email or password.")

    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Handle user signup via GET and POST requests."""
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if db.users.find_one({"email": email}):
            return render_template("signup.html", error="Email already taken.")

        db.users.insert_one({"email": email, "password": password})

        return redirect(url_for("login"))
    return render_template("signup.html")


@app.route("/logout")
@login_required
def logout():
    """Handle user logout and redirect to login page."""
    logout_user()
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
@login_required
def home():
    """Render home page and show uploaded image + matched professor image from MongoDB.
    saves history."""
    uploaded_image_base64 = None
    uploaded_image_mime = None
    matched_professor_image_base64 = None
    matched_professor_image_mime = "image/jpeg"
    matched_name = None
    status_message = None

    if request.method == "POST":
        original_name, image_bytes, uploaded_image_mime, error_message = (
            extract_uploaded_image()
        )

        if error_message:
            status_message = error_message
            return render_template(
                "home.html",
                uploaded_image_base64=uploaded_image_base64,
                uploaded_image_mime=uploaded_image_mime,
                matched_professor_image_base64=matched_professor_image_base64,
                matched_professor_image_mime=matched_professor_image_mime,
                matched_name=matched_name,
                status_message=status_message,
            )

        db.images.insert_one(
            {
                "user_id": current_user.id,
                "filename": original_name,
                "content_type": uploaded_image_mime,
                "photo": image_bytes,
                "created_at": datetime.now(),
            }
        )

        # prepare uploaded image for template
        uploaded_image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        try:
            response = requests.post(
                ML_SERVICE_URL,
                files={
                    "img1": (
                        original_name,
                        BytesIO(image_bytes),
                        uploaded_image_mime,
                    )
                },
                timeout=180,
            )

            if response.status_code == 200:
                data = response.json()
                matched_name = data["name"]

                # prefer image returned by ML service
                if data.get("photo"):
                    matched_photo_bytes = bytes.fromhex(data["photo"])
                    matched_professor_image_base64 = base64.b64encode(
                        matched_photo_bytes
                    ).decode("utf-8")
                    matched_professor_image_mime = data.get(
                        "matched_photo_mime", "image/jpeg"
                    )
                    status_message = "Match found."
                else:
                    # fallback mongo collection if needed
                    faculty_doc = db.faculty.find_one({"name": matched_name})

                    if faculty_doc and faculty_doc.get("photo"):
                        matched_photo_bytes = bytes(faculty_doc["photo"])
                        matched_professor_image_base64 = base64.b64encode(
                            matched_photo_bytes
                        ).decode("utf-8")

                        # if you later store faculty content type, use that instead
                        matched_professor_image_mime = faculty_doc.get(
                            "content_type", "image/jpeg"
                        )

                        status_message = "Match found."
                    else:
                        status_message = "Match found."

                save_history_entry(
                    user_email=current_user.email,
                    original_name=original_name,
                    uploaded_mime=uploaded_image_mime,
                    uploaded_bytes=image_bytes,
                    ml_data=data,
                )

            else:
                try:
                    error_data = response.json()
                    error_text = error_data.get("error", "Unknown ML error")
                except ValueError:
                    error_text = response.text or "Unknown ML error"

                status_message = (
                    f"ML service error: {response.status_code} - {error_text}"
                )

        except requests.RequestException as exc:
            status_message = f"Could not connect to ML service: {exc}"

    return render_template(
        "home.html",
        uploaded_image_base64=uploaded_image_base64,
        uploaded_image_mime=uploaded_image_mime,
        matched_professor_image_base64=matched_professor_image_base64,
        matched_professor_image_mime=matched_professor_image_mime,
        matched_name=matched_name,
        status_message=status_message,
    )


@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    """Show user info and upload history"""
    history_entries = load_user_history(current_user.email)

    return render_template(
        "dashboard.html", user=current_user, history_entries=history_entries
    )


# ======================== helper functions for history saving =========================
def guess_extension(content_type, original_name=None):
    """Guess file extension from MIME type or original filename"""
    if original_name and "." in original_name:
        ext = os.path.splitext(original_name)[1].lower()
        if ext:
            return ext

    ext = mimetypes.guess_extension(content_type or "")
    if ext == ".jpe":
        return ".jpg"
    return ext or ".bin"


def _object_id(value):
    """Convert a value to ObjectId or return None."""
    try:
        return ObjectId(value) if not isinstance(value, ObjectId) else value
    except (InvalidId, TypeError):
        return None


@app.route("/history/image/<entry_id>/<kind>", methods=["GET"])
@login_required
def history_image(entry_id, kind):
    """Serve a stored history image (uploaded or matched) from MongoDB."""
    if kind not in {"uploaded", "matched"}:
        abort(404)

    oid = _object_id(entry_id)
    if not oid:
        abort(404)

    doc = upload_history_collection.find_one({"_id": oid, "user_id": current_user.id})
    if not doc:
        abort(404)

    if kind == "uploaded":
        image_bytes = doc.get("uploaded_photo")
        content_type = doc.get("uploaded_content_type") or "application/octet-stream"
    else:
        image_bytes = doc.get("matched_photo")
        content_type = doc.get("matched_content_type") or "application/octet-stream"

    if not image_bytes:
        abort(404)

    return Response(bytes(image_bytes), mimetype=content_type)


def save_history_entry(
    user_email, original_name, uploaded_mime, uploaded_bytes, ml_data
):
    """
    Save search attempt to MongoDB.
    Returns the saved record dict.
    """
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S_%f")

    matched_image_bytes = None
    matched_image_mime = None
    photo_hex = ml_data.get("photo")
    if photo_hex:
        try:
            matched_image_bytes = bytes.fromhex(photo_hex)
            matched_image_mime = ml_data.get("matched_photo_mime", "image/jpeg")
        except ValueError:
            matched_image_bytes = None
            matched_image_mime = None

    record = {
        "timestamp": timestamp,
        "requested_at": now.strftime("%Y-%m-%d %H:%M"),
        "original_filename": original_name,
        "uploaded_image": {
            "content_type": uploaded_mime,
        },
        "match_result": {
            "name": ml_data.get("name"),
            "model": ml_data.get("model"),
            "distance_metric": ml_data.get("distance_metric"),
            "distance": ml_data.get("distance"),
            "threshold": ml_data.get("threshold"),
            "confidence": ml_data.get("confidence"),
            "similarity_score": ml_data.get("similarity_score"),
            "is_match": ml_data.get("is_match"),
            "source_face_box": ml_data.get("source_face_box"),
            "target_face_box": ml_data.get("target_face_box"),
            "matched_image_mime": matched_image_mime,
        },
    }
    doc = {
        "user_email": user_email,
        "user_id": current_user.id,
        "created_at": now,
        "timestamp": timestamp,
        "original_filename": original_name,
        "uploaded_photo": uploaded_bytes,
        "uploaded_content_type": uploaded_mime,
        "matched_photo": matched_image_bytes,
        "matched_content_type": matched_image_mime,
        "ml_result": record["match_result"],
    }

    inserted = upload_history_collection.insert_one(doc)
    entry_id = str(inserted.inserted_id)

    record["entry_id"] = entry_id
    record["uploaded_image"]["url"] = url_for(
        "history_image", entry_id=entry_id, kind="uploaded"
    )
    if matched_image_bytes:
        record["match_result"]["matched_image_url"] = url_for(
            "history_image", entry_id=entry_id, kind="matched"
        )
    else:
        record["match_result"]["matched_image_url"] = None

    return record


def load_user_history(user_email):
    """Load all saved history entries for a user from MongoDB, newest first."""
    entries = []
    cursor = upload_history_collection.find({"user_email": user_email}).sort(
        "created_at", -1
    )

    for doc in cursor:
        entry_id = str(doc["_id"])
        created_at = doc.get("created_at")
        requested_at = (
            created_at.strftime("%Y-%m-%d %H:%M")
            if isinstance(created_at, datetime)
            else None
        )
        match_result = doc.get("ml_result") or {}

        record = {
            "entry_id": entry_id,
            "timestamp": doc.get("timestamp"),
            "requested_at": doc.get("requested_at") or requested_at,
            "original_filename": doc.get("original_filename"),
            "uploaded_image": {
                "content_type": doc.get("uploaded_content_type"),
                "url": url_for("history_image", entry_id=entry_id, kind="uploaded"),
            },
            "match_result": {
                **match_result,
                "matched_image_url": (
                    url_for("history_image", entry_id=entry_id, kind="matched")
                    if doc.get("matched_photo")
                    else None
                ),
            },
        }
        entries.append(record)

    return entries


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
