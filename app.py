from flask import Flask, request, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import uuid
from google import genai
from google.genai import types
from math import radians, sin, cos, sqrt, atan2
from datetime import datetime

app = Flask(__name__, instance_relative_config=True)

# Configuration from environment variables
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Ensure instance folder exists
instance_path = app.instance_path
os.makedirs(instance_path, exist_ok=True)

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    'DATABASE_URL',
    f'sqlite:///{os.path.join(instance_path, "users.db")}'
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)
# ==========================
# Gemini AI
# ==========================

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    raise RuntimeError(
        "Missing GEMINI_API_KEY environment variable. "
        "Set it in PythonAnywhere Web app settings."
    )

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================
# User Model
# ==========================

class User(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), unique=True, nullable=False)

    password = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(20), nullable=False)
class Fundraiser(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(150), nullable=False)

    description = db.Column(db.Text, nullable=False)

    target_amount = db.Column(db.Float, nullable=False)

    collected_amount = db.Column(
        db.Float,
        default=0.0
    )

    image = db.Column(
        db.String(200),
        nullable=True
    )

    campaign_type = db.Column(
        db.String(50),
        nullable=False
    )

    # NGO who created campaign

    ngo_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    # Optional citizen complaint reference

    complaint_id = db.Column(
        db.Integer,
        db.ForeignKey("complaint.id"),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class Donation(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    fundraiser_id = db.Column(
        db.Integer,
        db.ForeignKey("fundraiser.id"),
        nullable=False
    )

    donor_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    amount = db.Column(
        db.Float,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

class VolunteerDrive(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(150), nullable=False)

    description = db.Column(db.Text, nullable=False)

    meeting_point = db.Column(db.String(200), nullable=False)

    contact = db.Column(db.String(20))

    drive_date = db.Column(db.String(30))

    drive_time = db.Column(db.String(20))

    volunteers_needed = db.Column(db.Integer)

    instructions = db.Column(db.Text)

    status = db.Column(db.String(20), default="Open")

    ngo_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id")
    )

class Complaint(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(150), nullable=False)

    description = db.Column(db.Text, nullable=False)

    category = db.Column(db.String(50), nullable=False)

    location = db.Column(db.String(255), nullable=False)

    latitude = db.Column(db.Float, nullable=False)

    longitude = db.Column(db.Float, nullable=False)

    image = db.Column(db.String(255))          # Before image

    status = db.Column(
        db.String(30),
        default="Pending"
    )

    citizen_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    # -------- New Fields --------

    assigned_to = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=True
    )

    assigned_role = db.Column(
        db.String(20),
        nullable=True
    )

    after_image = db.Column(
        db.String(255),
        nullable=True
    )

    completion_note = db.Column(
        db.Text,
        nullable=True
    )

    completed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    verified = db.Column(
        db.Boolean,
        default=False
    )

class Announcement(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(150), nullable=False)

    message = db.Column(db.Text, nullable=False)

    category = db.Column(db.String(30), default="General")

    posted_by = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    author = db.relationship("User")


def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in kilometers

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c
# ==========================
# Landing
# ==========================

@app.route("/")
def landing():

    if "logged_in" in session:
        return redirect(url_for("dashboard"))

    return render_template("landing.html")


# ==========================
# Authentication
# ==========================

@app.route("/auth/<role>", methods=["GET", "POST"])
def auth(role):

    if role not in ["citizen", "ngo", "municipal"]:
        return "Invalid Role"
    if "logged_in" in session:
        return redirect(url_for("dashboard"))
    colors = {
        "citizen": "primary",
        "ngo": "success",
        "municipal": "dark"
    }

    titles = {
        "citizen": "Citizen",
        "ngo": "NGO",
        "municipal": "Municipal Authority"
    }

    message = ""
    category = ""

    if request.method == "POST":

        action = request.form.get("action")

        username = request.form.get("username")

        password = request.form.get("password")

        # ---------------- Register ----------------

        if action == "register":

            confirm = request.form.get("confirm_password")

            if password != confirm:

                message = "Passwords do not match."

                category = "danger"

            elif User.query.filter_by(username=username).first():

                message = "Username already exists."

                category = "danger"

            else:

                hashed = generate_password_hash(password)

                new_user = User(
                    username=username,
                    password=hashed,
                    role=role
                )

                db.session.add(new_user)

                db.session.commit()

                message = "Registration successful. Please login."

                category = "success"

        # ---------------- Login ----------------

        elif action == "login":

            user = User.query.filter_by(
                username=username,
                role=role
            ).first()
            if user and check_password_hash(user.password, password):

                session["logged_in"] = True
                session["user_id"] = user.id
                session["username"] = user.username
                session["role"] = user.role

                return redirect(url_for("dashboard"))

            else:

                message = "Invalid username or password."

                category = "danger"

    return render_template(
        "auth.html",
        role=titles[role],
        role_value=role,
        color=colors[role],
        message=message,
        category=category
    )


# ==========================
# Dashboard
# ==========================
@app.route("/dashboard")
def dashboard():

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    role = session["role"]

    if role == "citizen":

        user_id = session["user_id"]

        pending = Complaint.query.filter_by(
            citizen_id=user_id,
            status="Pending"
        ).count()

        in_progress = Complaint.query.filter_by(
            citizen_id=user_id,
            status="In Progress"
        ).count()

        resolved = Complaint.query.filter_by(
            citizen_id=user_id,
            status="Completed"
        ).count()

        recent_complaints = Complaint.query.filter_by(
            citizen_id=user_id
        ).order_by(
            Complaint.id.desc()
        ).limit(5).all()

        announcements = Announcement.query.order_by(
            Announcement.id.desc()
        ).limit(5).all()

        return render_template(
            "citizen/dashboard.html",
            username=session["username"],
            pending=pending,
            in_progress=in_progress,
            resolved=resolved,
            recent_complaints=recent_complaints,
            announcements=announcements
        )

    elif session["role"] == "ngo":

        assigned_count = Complaint.query.filter_by(
            assigned_to=session["user_id"]
        ).count()

        completed_count = Complaint.query.filter_by(
            assigned_to=session["user_id"],
            status="Completed"
        ).count()

        active_drives = VolunteerDrive.query.filter_by(
            ngo_id=session["user_id"],
            status="Open"
        ).count()

        ngo_drive_ids = [
            d.id for d in VolunteerDrive.query.filter_by(
                ngo_id=session["user_id"]
            ).all()
        ]

        volunteers_joined = Volunteer.query.filter(
            Volunteer.drive_id.in_(ngo_drive_ids)
        ).count() if ngo_drive_ids else 0

        recent_issues = Complaint.query.filter_by(
            assigned_to=session["user_id"]
        ).order_by(
            Complaint.id.desc()
        ).limit(3).all()

        return render_template(
            "ngo/dashboard.html",
            username=session["username"],
            assigned_count=assigned_count,
            completed_count=completed_count,
            active_drives=active_drives,
            volunteers_joined=volunteers_joined,
            recent_issues=recent_issues
        )
    elif role == "municipal":

        total_complaints = Complaint.query.count()

        pending = Complaint.query.filter_by(status="Pending").count()

        in_progress = Complaint.query.filter_by(status="In Progress").count()

        completed = Complaint.query.filter_by(status="Completed").count()

        verified_count = Complaint.query.filter_by(verified=True).count()

        pending_verification = Complaint.query.filter_by(
            status="Completed",
            verified=False
        ).count()

        total_citizens = User.query.filter_by(role="citizen").count()

        total_ngos = User.query.filter_by(role="ngo").count()

        recent_complaints = Complaint.query.order_by(
            Complaint.id.desc()
        ).limit(5).all()

        recent_announcements = Announcement.query.order_by(
            Announcement.id.desc()
        ).limit(3).all()

        return render_template(
            "municipal/dashboard.html",
            username=session["username"],
            total_complaints=total_complaints,
            pending=pending,
            in_progress=in_progress,
            completed=completed,
            verified_count=verified_count,
            pending_verification=pending_verification,
            total_citizens=total_citizens,
            total_ngos=total_ngos,
            recent_complaints=recent_complaints,
            recent_announcements=recent_announcements
        )

    return redirect(url_for("landing"))


class Volunteer(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    drive_id = db.Column(
        db.Integer,
        db.ForeignKey("volunteer_drive.id"),
        nullable=False
    )

    citizen_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    joined_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    citizen = db.relationship("User")
    drive = db.relationship("VolunteerDrive")


@app.route("/view_volunteers/<int:drive_id>")
def view_volunteers(drive_id):

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    if session["role"] != "ngo":
        return redirect(url_for("dashboard"))

    drive = VolunteerDrive.query.get_or_404(drive_id)

    if drive.ngo_id != session["user_id"]:
        return redirect(url_for("volunteer_drives"))

    volunteers = Volunteer.query.filter_by(
        drive_id=drive.id
    ).order_by(
        Volunteer.joined_at.desc()
    ).all()

    return render_template(
        "ngo/view_volunteers.html",
        drive=drive,
        volunteers=volunteers,
        username=session["username"]
    )



@app.route("/volunteer_drives")
def volunteer_drives():

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    if session["role"] != "ngo":
        return redirect(url_for("dashboard"))

    drives = VolunteerDrive.query.filter_by(
        ngo_id=session["user_id"]
    ).order_by(
        VolunteerDrive.id.desc()
    ).all()

    total_volunteers = 0

    for drive in drives:
        drive.joined_count = Volunteer.query.filter_by(
            drive_id=drive.id
        ).count()

        total_volunteers += drive.joined_count

    return render_template(
        "ngo/volunteer_drives.html",
        username=session["username"],
        drives=drives,
        total_volunteers=total_volunteers
    )

@app.route("/drives")
def browse_drives():

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    if session["role"] != "citizen":
        return redirect(url_for("dashboard"))

    drives = VolunteerDrive.query.filter_by(
        status="Open"
    ).order_by(
        VolunteerDrive.id.desc()
    ).all()

    for drive in drives:
        drive.joined_count = Volunteer.query.filter_by(
            drive_id=drive.id
        ).count()

    joined_drive_ids = [
        v.drive_id for v in Volunteer.query.filter_by(
            citizen_id=session["user_id"]
        ).all()
    ]

    return render_template(
        "citizen/drives.html",
        username=session["username"],
        drives=drives,
        joined_drive_ids=joined_drive_ids
    )


@app.route("/join_drive/<int:drive_id>")
def join_drive(drive_id):

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    if session["role"] != "citizen":
        return redirect(url_for("dashboard"))

    drive = VolunteerDrive.query.get_or_404(drive_id)

    already_joined = Volunteer.query.filter_by(
        drive_id=drive.id,
        citizen_id=session["user_id"]
    ).first()

    joined_count = Volunteer.query.filter_by(
        drive_id=drive.id
    ).count()

    if (
        drive.status == "Open"
        and not already_joined
        and joined_count < drive.volunteers_needed
    ):

        volunteer = Volunteer(
            drive_id=drive.id,
            citizen_id=session["user_id"]
        )

        db.session.add(volunteer)
        db.session.commit()

    return redirect(url_for("browse_drives"))


@app.route("/close_drive/<int:drive_id>")
def close_drive(drive_id):

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    if session["role"] != "ngo":
        return redirect(url_for("dashboard"))

    drive = VolunteerDrive.query.get_or_404(drive_id)

    if drive.ngo_id != session["user_id"]:
        return redirect(url_for("volunteer_drives"))

    drive.status = "Closed"

    db.session.commit()

    return redirect(url_for("volunteer_drives"))

@app.route("/create_drive", methods=["GET", "POST"])
def create_drive():

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    if session["role"] != "ngo":
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        drive = VolunteerDrive(
            title=request.form["title"],
            description=request.form["description"],
            meeting_point=request.form["meeting_point"],
            contact=request.form["contact"],
            drive_date=request.form["date"],
            drive_time=request.form["time"],
            volunteers_needed=int(request.form["needed"]),
            instructions=request.form["instructions"],
            ngo_id=session["user_id"]
        )

        db.session.add(drive)
        db.session.commit()

        return redirect(url_for("volunteer_drives"))

    return render_template(
        "ngo/create_drive.html",
        username=session["username"]
    )

@app.route("/my_assigned")
def my_assigned():

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    complaints = Complaint.query.filter_by(
        assigned_to=session["user_id"]
    ).order_by(
        Complaint.id.desc()
    ).all()

    return render_template(
        "ngo/my_assigned.html",
        complaints=complaints,
        username=session["username"]
    )
@app.route("/fundraisers")
def fundraisers():

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    fundraisers = Fundraiser.query.order_by(
        Fundraiser.created_at.desc()
    ).all()

    if session.get("role") == "ngo":
        return render_template(
            "ngo/fundraisers.html",
            fundraisers=fundraisers
        )

    return render_template(
        "citizen/fundraisers.html",
        fundraisers=fundraisers,
        username=session.get("username")
    )
@app.route("/create_fundraiser", methods=["GET", "POST"])
def create_fundraiser():

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    user = User.query.get(session["user_id"])

    if not user or user.role != "ngo":
        return redirect(url_for("dashboard"))

    complaints = Complaint.query.filter(
        Complaint.assigned_to == user.id,
        Complaint.assigned_role == "ngo"
    ).all()

    if request.method == "POST":

        title = request.form.get("title")

        description = request.form.get("description")

        campaign_type = request.form.get(
            "campaign_type"
        )

        target_amount = float(
            request.form.get("target_amount")
        )

        complaint_id = request.form.get(
            "complaint_id"
        )

        image = request.files.get("image")

        filename = None

        if image and image.filename:

            filename = secure_filename(
                image.filename
            )

            image.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )


        fundraiser = Fundraiser(

            title=title,

            description=description,

            target_amount=target_amount,

            collected_amount=0,

            image=filename,

            campaign_type=campaign_type,

            ngo_id=user.id,

            complaint_id=(
                int(complaint_id)
                if complaint_id
                else None
            )

        )

        db.session.add(fundraiser)

        db.session.commit()


        return redirect(
            url_for("fundraisers")
        )


    return render_template(
        "ngo/create_fundraiser.html",
        complaints=complaints
    )
@app.route("/fundraiser_details/<int:fundraiser_id>")
def fundraiser_details(fundraiser_id):

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    fundraiser = Fundraiser.query.get_or_404(fundraiser_id)

    return render_template(
        "ngo/fundraiser_details.html",
        fundraiser=fundraiser,
        username=session.get("username")
    )


@app.route("/donate/<int:fundraiser_id>", methods=["POST"])
def donate(fundraiser_id):

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    fundraiser = Fundraiser.query.get_or_404(fundraiser_id)

    try:
        amount = float(request.form.get("amount", 0))
    except (ValueError, TypeError):
        amount = 0

    if amount <= 0:
        return redirect(
            url_for(
                "fundraiser_details",
                fundraiser_id=fundraiser.id
            )
        )

    # Prevent donation beyond target
    remaining = (
        fundraiser.target_amount
        - fundraiser.collected_amount
    )

    if amount > remaining:
        amount = remaining

    if amount <= 0:
        return redirect(
            url_for(
                "fundraiser_details",
                fundraiser_id=fundraiser.id
            )
        )

    # Create donation
    donation = Donation(
        fundraiser_id=fundraiser.id,
        donor_id=session["user_id"],
        amount=amount
    )

    db.session.add(donation)

    # Update collected amount
    fundraiser.collected_amount += amount

    db.session.commit()

    return redirect(
        url_for(
            "fundraiser_details",
            fundraiser_id=fundraiser.id
        )
    )

@app.route("/report", methods=["GET", "POST"])
def report():

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    if session["role"] != "citizen":
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        file = request.files.get("image")

        filename = ""

        if file and file.filename != "":

            filename = secure_filename(
                str(uuid.uuid4()) + "_" + file.filename
            )

            file.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

        complaint = Complaint(
            title=request.form["title"],
            description=request.form["description"],
            category=request.form["category"],
            location=request.form["location"],
            latitude=float(request.form.get("latitude") or 0),
            longitude=float(request.form.get("longitude") or 0),
            image=filename,
            citizen_id=session["user_id"]
        )

        db.session.add(complaint)

        db.session.commit()

        return redirect(url_for("dashboard"))

    return render_template("citizen/report.html")
@app.route("/analyze_issue", methods=["POST"])
def analyze_issue():

    if "logged_in" not in session:
        return {
            "success": False,
            "error": "Please login first."
        }, 401

    if session.get("role") != "citizen":
        return {
            "success": False,
            "error": "Only citizens can report issues."
        }, 403

    file = request.files.get("image")

    if not file or file.filename == "":
        return {
            "success": False,
            "error": "Please upload an image."
        }, 400

    try:

        image_bytes = file.read()

        mime_type = file.mimetype or "image/jpeg"

        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=mime_type
        )

        prompt = """
You are an AI assistant for CivicConnect.

Analyze the uploaded image and identify the civic issue.

Return ONLY valid JSON in exactly this format:

{
    "title": "short issue title",
    "description": "clear description of the issue",
    "category": "one category"
}

IMPORTANT:
The category MUST be EXACTLY ONE of these values:

"Garbage"
"Pothole"
"Street Light"
"Water Leakage"
"Sewage"
"Illegal Dumping"
"Other"

Do not use any other category.
Do not add punctuation.
Do not use plural forms.
Do not return markdown.
Return JSON only.

Rules:
- Analyze only what is visible in the image.
- Do not invent information.
- Keep the title short.
- Make the description suitable for a civic complaint.
"""
        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=[
                image_part,
                prompt
            ]
        )

        result_text = response.text.strip()

        # Remove markdown fences if Gemini adds them
        if result_text.startswith("```"):
            result_text = result_text.replace("```json", "")
            result_text = result_text.replace("```", "")
            result_text = result_text.strip()

        import json

        result = json.loads(result_text)

        return {
            "success": True,
            "data": result
        }

    except Exception as e:

        print("Gemini Error:", e)

        return {
            "success": False,
            "error": "Could not analyze the image. Please fill the form manually."
        }, 500
# ==========================
# My Complaints
# ==========================

@app.route("/my_complaints")
def my_complaints():

    # User must be logged in
    if "logged_in" not in session:
        return redirect(url_for("landing"))

    # Only citizens can access this page
    if session.get("role") != "citizen":
        return redirect(url_for("dashboard"))

    # Current logged in user's ID
    user_id = session["user_id"]

    # Fetch ONLY this user's complaints
    complaints = Complaint.query.filter_by(
        citizen_id=user_id
    ).order_by(Complaint.id.desc()).all()

    # Statistics
    pending = Complaint.query.filter_by(
        citizen_id=user_id,
        status="Pending"
    ).count()

    in_progress = Complaint.query.filter_by(
        citizen_id=user_id,
        status="In Progress"
    ).count()

    resolved = Complaint.query.filter_by(
        citizen_id=user_id,
        status="Completed"
    ).count()

    return render_template(
        "citizen/my_complaints.html",
        username=session["username"],
        complaints=complaints,
        pending=pending,
        in_progress=in_progress,
        resolved=resolved
    )
# ==========================
# Profile
# ==========================

@app.route("/profile", methods=["GET", "POST"])
def profile():

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    user = User.query.get(session["user_id"])

    if not user:
        session.clear()
        return redirect(url_for("landing"))

    message = ""
    category = ""

    if request.method == "POST":

        username = request.form.get("username", "").strip()

        current_password = request.form.get(
            "current_password",
            ""
        )

        new_password = request.form.get(
            "new_password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )


        # =================================
        # USERNAME
        # =================================

        if not username:

            message = "Username cannot be empty."
            category = "danger"

        else:

            existing_user = User.query.filter(
                User.username == username,
                User.id != user.id
            ).first()


            if existing_user:

                message = "Username already exists."
                category = "danger"

            else:

                # Update username

                user.username = username


                # =================================
                # PASSWORD CHANGE
                # =================================

                if new_password or confirm_password:

                    # Current password is REQUIRED

                    if not current_password:

                        message = (
                            "Enter your current password "
                            "to change your password."
                        )

                        category = "danger"

                    # Verify current password

                    elif not check_password_hash(
                        user.password,
                        current_password
                    ):

                        message = "Current password is incorrect."
                        category = "danger"

                    # Check new passwords

                    elif new_password != confirm_password:

                        message = "New passwords do not match."
                        category = "danger"

                    # Minimum password length

                    elif len(new_password) < 6:

                        message = (
                            "New password must contain "
                            "at least 6 characters."
                        )

                        category = "danger"

                    # Everything is valid

                    else:

                        user.password = generate_password_hash(
                            new_password
                        )

                        message = (
                            "Profile and password updated successfully."
                        )

                        category = "success"


                else:

                    message = "Profile updated successfully."
                    category = "success"


                # =================================
                # SAVE
                # =================================

                if category == "success":

                    db.session.commit()

                    session["username"] = user.username


    return render_template(
        "citizen/profile.html",
        username=user.username,
        role=user.role,
        message=message,
        category=category
    )

@app.route("/complete_issue/<int:complaint_id>", methods=["GET", "POST"])
def complete_issue(complaint_id):

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    complaint = Complaint.query.get_or_404(complaint_id)

    if complaint.assigned_to != session["user_id"]:
        return redirect(url_for("nearby"))

    if request.method == "POST":

        file = request.files.get("after_image")

        filename = ""

        if file and file.filename:

            filename = secure_filename(
                str(uuid.uuid4()) + "_" + file.filename
            )

            file.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    filename
                )
            )

        complaint.after_image = filename

        complaint.completion_note = request.form["completion_note"]

        complaint.completed_at = datetime.utcnow()

        complaint.status = "Completed"

        db.session.commit()

        return redirect(url_for("nearby"))

    return render_template(
        "complete_issue.html",
        complaint=complaint,
        username=session["username"]
    )

@app.route("/nearby", methods=["GET", "POST"])
def nearby():

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    complaints = []

    if request.method == "POST":

        user_lat = float(request.form["latitude"])
        user_lon = float(request.form["longitude"])

        all_complaints = Complaint.query.filter(
            Complaint.status != "Verified"
        ).all()

        for complaint in all_complaints:

            distance = haversine(
                user_lat,
                user_lon,
                complaint.latitude,
                complaint.longitude
            )

            if distance <= 20:

                complaint.distance = round(distance, 2)

                complaints.append(complaint)

        complaints.sort(key=lambda x: x.distance)

    return render_template(
        "nearby.html",
        complaints=complaints,
        username=session["username"]
    )
@app.route("/take_issue/<int:complaint_id>")
def take_issue(complaint_id):

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    complaint = Complaint.query.get_or_404(complaint_id)

    # Only pending complaints can be taken
    if complaint.status != "Pending":
        return redirect(url_for("nearby"))

    complaint.status = "In Progress"

    complaint.assigned_to = session["user_id"]

    complaint.assigned_role = session["role"]

    db.session.commit()

    return redirect(url_for("nearby"))

# ==========================
# Municipal
# ==========================

@app.route("/municipal/complaints")
def municipal_complaints():

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    if session["role"] != "municipal":
        return redirect(url_for("dashboard"))

    status_filter = request.args.get("status", "All")
    category_filter = request.args.get("category", "All")

    query = Complaint.query

    if status_filter != "All":
        query = query.filter_by(status=status_filter)

    if category_filter != "All":
        query = query.filter_by(category=category_filter)

    complaints = query.order_by(Complaint.id.desc()).all()

    categories = [
        row[0] for row in db.session.query(Complaint.category).distinct().all()
    ]

    ngos = User.query.filter_by(role="ngo").all()

    return render_template(
        "municipal/complaints.html",
        username=session["username"],
        complaints=complaints,
        categories=categories,
        ngos=ngos,
        status_filter=status_filter,
        category_filter=category_filter
    )


@app.route("/municipal/assign/<int:complaint_id>", methods=["POST"])
def assign_complaint(complaint_id):

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    if session["role"] != "municipal":
        return redirect(url_for("dashboard"))

    complaint = Complaint.query.get_or_404(complaint_id)

    ngo_id = request.form.get("ngo_id")

    if complaint.status == "Pending" and ngo_id:

        ngo_user = User.query.filter_by(id=ngo_id, role="ngo").first()

        if ngo_user:

            complaint.assigned_to = ngo_user.id
            complaint.assigned_role = "ngo"
            complaint.status = "In Progress"

            db.session.commit()

    return redirect(url_for("municipal_complaints"))


@app.route("/verify_issue/<int:complaint_id>")
def verify_issue(complaint_id):

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    if session["role"] != "municipal":
        return redirect(url_for("dashboard"))

    complaint = Complaint.query.get_or_404(complaint_id)

    return render_template(
        "municipal/verify_issue.html",
        complaint=complaint,
        username=session["username"]
    )


@app.route("/verify_issue/<int:complaint_id>/confirm")
def verify_issue_confirm(complaint_id):

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    if session["role"] != "municipal":
        return redirect(url_for("dashboard"))

    complaint = Complaint.query.get_or_404(complaint_id)

    if complaint.status == "Completed":
        complaint.verified = True
        db.session.commit()

    return redirect(url_for("municipal_complaints"))


@app.route("/announcements", methods=["GET", "POST"])
def announcements():

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    if request.method == "POST":

        if session["role"] != "municipal":
            return redirect(url_for("dashboard"))

        announcement = Announcement(
            title=request.form["title"],
            message=request.form["message"],
            category=request.form.get("category") or "General",
            posted_by=session["user_id"]
        )

        db.session.add(announcement)
        db.session.commit()

        return redirect(url_for("announcements"))

    all_announcements = Announcement.query.order_by(
        Announcement.id.desc()
    ).all()

    if session["role"] == "municipal":
        return render_template(
            "municipal/announcements.html",
            username=session["username"],
            announcements=all_announcements
        )

    return redirect(url_for("dashboard"))


@app.route("/delete_announcement/<int:announcement_id>")
def delete_announcement(announcement_id):

    if "logged_in" not in session:
        return redirect(url_for("landing"))

    if session["role"] != "municipal":
        return redirect(url_for("dashboard"))

    announcement = Announcement.query.get_or_404(announcement_id)

    if announcement.posted_by == session["user_id"]:
        db.session.delete(announcement)
        db.session.commit()

    return redirect(url_for("announcements"))


# ==========================
# Short Routes
# ==========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))

@app.route("/citizen")
def citizen():
    return redirect(url_for("auth", role="citizen"))


@app.route("/ngo")
def ngo():
    return redirect(url_for("auth", role="ngo"))


@app.route("/municipal")
def municipal():
    return redirect(url_for("auth", role="municipal"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    
    # Use debug=False for production
    app.run(debug=os.environ.get('FLASK_DEBUG', 'False') == 'True')