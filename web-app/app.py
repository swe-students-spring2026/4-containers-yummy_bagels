"""Web app for the project"""

import base64
from io import BytesIO
import os
import requests
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
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
    """Render home page and show uploaded image + matched professor image from MongoDB."""
    uploaded_image_base64 = None
    uploaded_image_mime = None
    matched_professor_image_base64 = None
    matched_professor_image_mime = "image/jpeg"
    matched_name = None
    status_message = None

    if request.method == "POST":
        uploaded_file = request.files.get("image")

        if not uploaded_file or uploaded_file.filename == "":
            status_message = "Please choose an image file"
            return render_template(
                "home.html",
                uploaded_image_base64=uploaded_image_base64,
                uploaded_image_mime=uploaded_image_mime,
                matched_professor_image_base64=matched_professor_image_base64,
                matched_professor_image_mime=matched_professor_image_mime,
                matched_name=matched_name,
                status_message=status_message,
            )

        if not allowed_file(uploaded_file.filename):
            status_message = "Only PNG, JPG, and JPEG files are allowed"
            return render_template(
                "home.html",
                uploaded_image_base64=uploaded_image_base64,
                uploaded_image_mime=uploaded_image_mime,
                matched_professor_image_base64=matched_professor_image_base64,
                matched_professor_image_mime=matched_professor_image_mime,
                matched_name=matched_name,
                status_message=status_message,
            )

        original_name = secure_filename(uploaded_file.filename)
        image_bytes = uploaded_file.read()
        uploaded_image_mime = uploaded_file.mimetype or "image/jpeg"

        # store uploaded image in MongoDB
        db.images.insert_one(
            {
                "user_id": current_user.id,
                "filename": original_name,
                "content_type": uploaded_image_mime,
                "photo": image_bytes,
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
                matched_name = response.text.strip()

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
                    status_message = (
                        f"Match found, but no faculty image stored for {matched_name}."
                    )
            else:
                status_message = f"ML service error: {response.status_code}"

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


@app.route("/dashboard")
@login_required
def dashboard():
    """render dashboard page"""
    return render_template("dashboard.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
