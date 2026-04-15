"""Web app for the project"""

import os
import uuid
import re
import unicodedata
import requests
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory,
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
UPLOAD_FOLDER = os.path.join("static", "temp_uploads")
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:5001/find-lookalike")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
FACULTY_IMAGE_FOLDER = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "..", "machine-learning-client", "faculty_images"
    )
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

# Flask login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # redirect here if not logged in


class User(UserMixin):
    """Represents a user for Flask-Login integration."""

    def __init__(self, user):
        self.id = user["_id"]
        self.email = user["email"]


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
    """render home page"""
    uploaded_image_url = None
    matched_professor_image_url = None
    matched_name = None
    status_message = None

    if request.method == "POST":
        uploaded_file = request.files.get("image")
        if not uploaded_file or uploaded_file.filename == "":
            status_message = "Please choose an image file"
            return render_template(
                "home.html",
                uploaded_image_url=uploaded_image_url,
                matched_professor_image_url=matched_professor_image_url,
                matched_name=matched_name,
                status_message=status_message,
            )
        if not allowed_file(uploaded_file.filename):
            status_message = "Only PNG, JPG, and JPEG files are allowed"
            return render_template(
                "home.html",
                uploaded_image_url=uploaded_image_url,
                matched_professor_image_url=matched_professor_image_url,
                matched_name=matched_name,
                status_message=status_message,
            )

        # save uploaded file temporarily
        original_name = secure_filename(uploaded_file.filename)
        ext = original_name.rsplit(".", 1)[1].lower()
        unique_filename = f"{current_user.id}_{uuid.uuid4().hex}.{ext}"
        temp_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        uploaded_file.save(temp_path)

        uploaded_image_url = url_for(
            "static", filename=f"temp_uploads/{unique_filename}"
        )

        try:
            with open(temp_path, "rb") as img_file:
                response = requests.post(
                    ML_SERVICE_URL,
                    files={"img1": img_file},
                    timeout=180,
                )
            if response.status_code == 200:
                matched_name = response.text.strip()
                matched_filename = safe_faculty_filename(matched_name)
                matched_professor_image_url = url_for(
                    "faculty_image", filename=matched_filename
                )
                status_message = "Match found."
            else:
                status_message = f"ML service error: {response.status_code}"

        except requests.RequestException as exc:
            status_message = f"Could not connect to ML service: {exc}"

    return render_template(
        "home.html",
        uploaded_image_url=uploaded_image_url,
        matched_professor_image_url=matched_professor_image_url,
        matched_name=matched_name,
        status_message=status_message,
    )


@app.route("/dashboard")
@login_required
def dashboard():
    """render dashboard page"""
    return render_template("dashboard.html")


# for returning faculty images
@app.route("/faculty-images/<path:filename>")
@login_required
def faculty_image(filename):
    """Serve faculty images from the machine-learning-client folder."""
    return send_from_directory(FACULTY_IMAGE_FOLDER, filename)


# helper for file renaming
def safe_faculty_filename(name):
    """Convert professor name to the image filename used on disk."""
    normalized = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    )
    normalized = normalized.replace(" ", "_")
    normalized = re.sub(r"[^A-Za-z0-9_-]", "", normalized)
    return normalized + ".jpg"


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
