from pathlib import Path
import csv
import io
import hashlib
import secrets
import smtplib
import shutil
import re
import time
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    Response,
    flash,
    redirect,
    render_template,
    request,
    jsonify,
    session,
    url_for,
    send_file,
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from config import Config
from database.db import (
    get_connection,
    create_user,
    record_login_activity,
    get_user_analytics,
    update_last_login,
    update_last_seen,
)
from services.link_service import download_spreadsheet

from services.admin_settings import (
    generate_admin_registration_code,
    verify_admin_registration_code,
)
from services.data_service import (
    MODULES,
    create_dataset,
    delete_upload,
    get_all_datasets,
    get_all_rows,
    get_record_counts,
    get_report,
    get_user_datasets,
    get_module_data,
    build_module_report,
    normalize_module,
    normalize_category,
    normalize_department,
    is_valid_department,
    normalize_study_year,
    normalize_reporting_period,
    build_reporting_value,
    DEPARTMENTS,
    REPORTING_PERIODS,
    MONTHS,
    SEMESTERS,
    get_department_summary,
    read_spreadsheet,
    detect_source_type,
    resolve_submission_file,
    classify_row,
    is_documentation_sheet,
    normalize_text,
)


main_bp = Blueprint(
    "main",
    __name__
)


# =========================================================
# AUTHENTICATION
# =========================================================

def _request_ip():
    """Return the direct client address available to Flask."""
    return request.remote_addr or "unknown"


def _request_user_agent():
    return request.headers.get("User-Agent", "")[:1000]

def get_current_user():

    user_id = session.get("user_id")

    if not user_id:
        return None

    connection = get_connection()

    try:

        row = connection.execute(
            """
            SELECT
                id,
                name,
                email,
                role,
                created_at
            FROM users
            WHERE id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        if not row:
            return None

        # Keep the last-seen timestamp current for the admin activity dashboard.
        connection.execute(
            """
            UPDATE users
            SET last_seen_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (user_id,),
        )
        connection.commit()

        return dict(row)

    finally:

        connection.close()


# =========================================================
# LOGIN REQUIRED
# =========================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        user = get_current_user()

        if not user:

            flash(
                "Please login first.",
                "warning"
            )

            return redirect(
                url_for(
                    "main.login",
                    next=request.path
                )
            )

        return function(
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# ADMIN REQUIRED
# =========================================================

def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        user = get_current_user()

        if not user:

            flash(
                "Please login first.",
                "warning"
            )

            return redirect(
                url_for(
                    "main.login",
                    next=request.path
                )
            )

        if user["role"] != "admin":

            flash(
                "Administrator access required.",
                "danger"
            )

            return redirect(
                url_for(
                    "main.home"
                )
            )

        return function(
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# SAFE REDIRECT
# =========================================================

def safe_next_url(value):

    if not value:
        return None

    if (
        value.startswith("/")
        and not value.startswith("//")
    ):
        return value

    return None


# =========================================================
# GLOBAL TEMPLATE VARIABLES
# =========================================================

@main_bp.app_context_processor
def inject_user():

    return {
        "current_user": get_current_user(),
        "modules": MODULES,
        "departments": DEPARTMENTS,
        "reporting_periods": REPORTING_PERIODS,
        "months": MONTHS,
        "semesters": SEMESTERS,
    }


# =========================================================
# HOME
# =========================================================

@main_bp.route("/")
def home():

    return render_template(
        "index.html",
        modules=MODULES,
    )


# =========================================================
# MODULES
# =========================================================

@main_bp.route("/modules")
def modules_page():

    return redirect(
        url_for("main.home")
        + "#modules"
    )


# =========================================================
# ABOUT
# =========================================================

@main_bp.route("/about")
def about():

    return render_template(
        "about.html"
    )


# =========================================================
# PUBLIC REGISTRATION DISABLED
# =========================================================

@main_bp.route("/register", methods=["GET", "POST"])
def register():
    """Public self-registration is disabled.

    All UCE Connect accounts must be created by an existing administrator
    from the Admin -> User Analytics page.
    """
    flash(
        "Public registration is disabled. Please contact an administrator to create your account.",
        "warning",
    )
    return redirect(url_for("main.login"))


# =========================================================
# LOGIN
# =========================================================

@main_bp.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "GET":

        return render_template(
            "login.html"
        )


    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )


    connection = get_connection()

    try:

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            COLLATE NOCASE
            LIMIT 1
            """,
            (email,),
        ).fetchone()

    finally:

        connection.close()


    if (
        not user
        or not check_password_hash(
            user["password_hash"],
            password
        )
    ):

        record_login_activity(
            event_type="failed_login",
            user_id=user["id"] if user else None,
            email_attempted=email,
            ip_address=_request_ip(),
            user_agent=_request_user_agent(),
        )

        flash(
            "Invalid email or password.",
            "danger"
        )

        return render_template(
            "login.html"
        )


    update_last_login(user["id"])

    record_login_activity(
        event_type="login",
        user_id=user["id"],
        email_attempted=email,
        ip_address=_request_ip(),
        user_agent=_request_user_agent(),
    )

    session.clear()

    session["user_id"] = user["id"]

    session["user_name"] = user["name"]

    session["user_role"] = user["role"]


    flash(
        f"Welcome, {user['name']}.",
        "success"
    )


    next_url = safe_next_url(
        request.args.get("next")
    )

    if next_url:

        return redirect(
            next_url
        )


    if user["role"] == "admin":

        return redirect(
            url_for(
                "main.admin"
            )
        )


    return redirect(
        url_for(
            "main.home"
        )
    )


def _send_password_reset_email(
    recipient,
    recipient_name,
    reset_url,
):
    """Send the password-reset link using the configured SMTP server."""

    host = Config.SMTP_HOST

    if not host:
        raise RuntimeError(
            "Password reset email is not configured. "
            "Set UCE_SMTP_HOST and the related SMTP settings."
        )

    message = EmailMessage()
    message["Subject"] = "UCE Connect - Password Reset"
    message["From"] = Config.SMTP_FROM_EMAIL
    message["To"] = recipient

    greeting = (
        f"Hello {recipient_name},"
        if recipient_name
        else "Hello,"
    )

    message.set_content(
        f"""{greeting}

We received a request to reset your UCE Connect password.

Use the link below to create a new password:
{reset_url}

This link expires in {Config.PASSWORD_RESET_MINUTES} minutes and can be used only once.

If you did not request this, you can safely ignore this email.

Regards,
UCE Connect
"""
    )

    if Config.SMTP_USE_SSL:
        with smtplib.SMTP_SSL(
            host,
            Config.SMTP_PORT,
            timeout=30,
        ) as server:
            if Config.SMTP_USERNAME:
                server.login(
                    Config.SMTP_USERNAME,
                    Config.SMTP_PASSWORD,
                )
            server.send_message(message)
        return

    with smtplib.SMTP(
        host,
        Config.SMTP_PORT,
        timeout=30,
    ) as server:
        server.ehlo()

        if Config.SMTP_USE_TLS:
            server.starttls()
            server.ehlo()

        if Config.SMTP_USERNAME:
            server.login(
                Config.SMTP_USERNAME,
                Config.SMTP_PASSWORD,
            )

        server.send_message(message)


# =========================================================
# PASSWORD RESET
# =========================================================

def _hash_reset_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@main_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form.get("email", "").strip().lower()

    if not email:
        flash("Please enter your email address.", "danger")
        return render_template("forgot_password.html")

    connection = get_connection()

    try:
        user = connection.execute(
            """
            SELECT id, name, email
            FROM users
            WHERE email = ? COLLATE NOCASE
            LIMIT 1
            """,
            (email,),
        ).fetchone()

        if not user:
            flash("No account was found with that email address.", "danger")
            return render_template("forgot_password.html")

        # Invalidate older unused reset links for this account.
        connection.execute(
            """
            UPDATE password_reset_tokens
            SET used_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND used_at IS NULL
            """,
            (user["id"],),
        )

        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_reset_token(raw_token)
        minutes = Config.PASSWORD_RESET_MINUTES
        expires_at = (
            datetime.now(timezone.utc) + timedelta(minutes=minutes)
        ).isoformat()

        connection.execute(
            """
            INSERT INTO password_reset_tokens
                (user_id, token_hash, expires_at)
            VALUES (?, ?, ?)
            """,
            (user["id"], token_hash, expires_at),
        )
        connection.commit()

        reset_url = url_for(
            "main.reset_password",
            token=raw_token,
            _external=True,
        )

        try:
            _send_password_reset_email(
                user["email"],
                user["name"],
                reset_url,
            )

        except Exception as email_error:
            # SMTP is optional during local development. If email is not
            # configured, keep the token valid and expose the reset link
            # only on localhost (or when explicitly enabled).
            print(
                "PASSWORD RESET EMAIL ERROR:",
                repr(email_error),
            )

            host_only = request.host.split(":", 1)[0].lower()
            is_localhost = host_only in {
                "127.0.0.1",
                "localhost",
                "::1",
            }

            if Config.EXPOSE_RESET_LINKS or is_localhost:
                flash(
                    "Email delivery is not configured for this local "
                    "development server. Use the reset link below.",
                    "info",
                )
                flash(
                    f"Development password reset link: {reset_url}",
                    "info",
                )
                return render_template(
                    "forgot_password.html",
                    reset_url=reset_url,
                    dev_mode=True,
                )

            # Production: invalidate the token when delivery fails.
            connection.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = CURRENT_TIMESTAMP
                WHERE token_hash = ?
                  AND used_at IS NULL
                """,
                (token_hash,),
            )
            connection.commit()

            raise RuntimeError(
                "Password reset email could not be sent."
            ) from email_error

        flash(
            "If an account exists for that email, a password reset link has "
            "been sent to the registered email address.",
            "success",
        )
        return redirect(url_for("main.forgot_password"))

    except Exception as error:
        try:
            connection.rollback()
        except Exception:
            pass

        print(
            "PASSWORD RESET ERROR:",
            repr(error),
        )

        flash(
            "Unable to process the password reset request. "
            "Please try again.",
            "danger",
        )
        return render_template("forgot_password.html")
    finally:
        connection.close()


@main_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    token_hash = _hash_reset_token(token)
    connection = get_connection()

    try:
        reset_record = connection.execute(
            """
            SELECT id, user_id, expires_at, used_at
            FROM password_reset_tokens
            WHERE token_hash = ?
            LIMIT 1
            """,
            (token_hash,),
        ).fetchone()

        if not reset_record:
            flash(
                "This password reset link is invalid or has expired.",
                "danger",
            )
            return redirect(url_for("main.forgot_password"))

        if reset_record["used_at"]:
            flash(
                "This password reset link has already been used.",
                "danger",
            )
            return redirect(url_for("main.forgot_password"))

        try:
            expires_at = datetime.fromisoformat(
                reset_record["expires_at"].replace("Z", "+00:00")
            )
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            expires_at = datetime.min.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) >= expires_at:
            flash(
                "This password reset link is invalid or has expired.",
                "danger",
            )
            return redirect(url_for("main.forgot_password"))

        if request.method == "GET":
            return render_template("reset_password.html")

        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(password) < 8:
            flash(
                "Password must contain at least 8 characters.",
                "danger",
            )
            return render_template("reset_password.html")

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("reset_password.html")

        connection.execute(
            """
            UPDATE users
            SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                generate_password_hash(password),
                reset_record["user_id"],
            ),
        )

        connection.execute(
            """
            UPDATE password_reset_tokens
            SET used_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reset_record["id"],),
        )

        connection.execute(
            """
            UPDATE password_reset_tokens
            SET used_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
              AND used_at IS NULL
              AND id <> ?
            """,
            (
                reset_record["user_id"],
                reset_record["id"],
            ),
        )

        connection.commit()

        flash(
            "Your password has been reset successfully. "
            "Please login with your new password.",
            "success",
        )
        return redirect(url_for("main.login"))

    except Exception:
        connection.rollback()
        flash(
            "Unable to reset the password. Please request a new link.",
            "danger",
        )
        return redirect(url_for("main.forgot_password"))
    finally:
        connection.close()


# =========================================================
# LOGOUT
# =========================================================

@main_bp.route("/logout")
def logout():

    user_id = session.get("user_id")

    if user_id:
        record_login_activity(
            event_type="logout",
            user_id=user_id,
            ip_address=_request_ip(),
            user_agent=_request_user_agent(),
        )

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for(
            "main.home"
        )
    )


# =========================================================
# USER - EXPORT OFFICIAL REPORT
# =========================================================

@main_bp.route(
    "/download-template",
    methods=["GET"]
)
@main_bp.route(
    "/export-report",
    methods=["GET"]
)
@login_required
def export_report():
    """Download the official Excel input template.

    This is intentionally a template, not a dynamic database export.
    Users prepare their spreadsheet in this format and then upload it or
    submit its public/downloadable link.
    """

    report_path = (
        Path(current_app.root_path)
        / "static"
        / "reports"
        / "UCE_IQAC_Audit_Report.xlsx"
    )

    if not report_path.exists():
        flash(
            "The official report file is not available.",
            "danger"
        )
        return redirect(
            url_for("main.submit_link")
        )

    return send_file(
        report_path,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        as_attachment=True,
        download_name="UCE_IQAC_Audit_Report.xlsx",
    )


# =========================================================
# USER - IMPORT PREVIEW HELPERS
# =========================================================

def _row_cell(row, aliases):
    """Return the first non-empty spreadsheet value matching any header alias."""
    if hasattr(row, "items"):
        values = row.items()
    else:
        values = []

    alias_set = {normalize_text(alias) for alias in aliases}

    for key, value in values:
        if normalize_text(key) not in alias_set:
            continue
        if value is None:
            continue
        text = str(value).strip()
        if not text or text.lower() in {"nan", "nat", "none"}:
            continue
        return text

    return ""


def _detect_row_context(row):
    """Detect department/year/reporting period information from one row."""
    department = normalize_department(
        _row_cell(
            row,
            ["department", "department name", "dept", "group", "department/group"],
        )
    )

    year = _row_cell(
        row,
        [
            "year",
            "reporting year",
            "reporting_year",
            "academic year",
            "academic_year",
            "calendar year",
        ],
    )

    # Accept 2025, 2026 etc. and also values such as 2025-26.
    year_match = re.search(r"(?:19|20)\d{2}", year) if year else None
    normalized_year = year_match.group(0) if year_match else year

    period_raw = _row_cell(
        row,
        [
            "period",
            "period type",
            "period_type",
            "reporting period",
            "reporting_period",
            "frequency",
            "reporting type",
            "reporting_type",
        ],
    )

    month = _row_cell(
        row,
        ["month", "reporting month", "reporting_month"],
    )

    semester = _row_cell(
        row,
        ["semester", "reporting semester", "reporting_semester", "sem"],
    )

    period_lower = period_raw.lower()

    if "semester" in period_lower or re.search(r"\bsem(?:ester)?\s*[12]\b", period_lower):
        period = "Semester"
    elif any(token in period_lower for token in ["monthly", "month"]):
        period = "Monthly"
    elif any(token in period_lower for token in ["yearly", "annual", "year"]):
        period = "Yearly"
    else:
        period = normalize_reporting_period(period_raw)

    if not period:
        if semester:
            period = "Semester"
        elif month:
            period = "Monthly"
        elif normalized_year:
            period = "Yearly"

    if not semester and period == "Semester":
        sem_match = re.search(r"(?:semester|sem)\s*([12])", period_lower)
        if sem_match:
            semester = f"Semester {sem_match.group(1)}"

    if not month and period == "Monthly":
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        for month_name in month_names:
            if month_name.lower() in period_lower:
                month = month_name
                break

    detail = semester if period == "Semester" else month if period == "Monthly" else ""

    if period == "Yearly":
        reporting_value = normalized_year
    elif period == "Semester" and normalized_year:
        # Automatic Consolidation files may provide only `Period Type = Semester`
        # and `Reporting Year`; do not reject the row just because there is no
        # separate reporting-semester column.
        reporting_value = f"{detail} - {normalized_year}" if detail else f"Semester - {normalized_year}"
    elif period == "Monthly" and normalized_year:
        # Automatic Consolidation files may provide only `Period Type = Monthly`
        # and `Reporting Year`; the exact month is optional in that format.
        reporting_value = f"{detail} {normalized_year}" if detail else f"Monthly {normalized_year}"
    else:
        reporting_value = ""

    valid = bool(
        department
        and normalized_year
        and period in REPORTING_PERIODS
        and reporting_value
    )

    return {
        "department": department,
        "year": normalized_year,
        "period": period,
        "detail": detail,
        "reporting_value": reporting_value,
        "valid": valid,
    }


# =========================================================
# USER - IMPORT PREVIEW
# =========================================================

def _cleanup_stale_preview_files(max_age_hours=2):
    """Remove abandoned preview files left by closed tabs or failed requests."""
    preview_dir = Path(current_app.root_path) / "instance" / "preview_uploads"
    if not preview_dir.exists():
        return

    cutoff = time.time() - (max_age_hours * 60 * 60)
    for path in preview_dir.iterdir():
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            # A file being used by another request should not break import.
            continue


@main_bp.route(
    "/submit-link/preview",
    methods=["POST"]
)
@login_required
def submit_link_preview():
    """Validate an uploaded/link spreadsheet without importing it.

    The preview is deliberately database-free. The source file is stored in a
    temporary preview directory and is only imported after the user presses
    Confirm Import.
    """

    from collections import Counter

    _cleanup_stale_preview_files()

    source_url = request.form.get("source_url", "").strip()
    upload = request.files.get("spreadsheet_file")
    source_type = request.form.get("source_type", "file").strip().lower()
    if source_type not in {"file", "link"}:
        source_type = "file"

    # -----------------------------------------------------
    # Validate source
    # -----------------------------------------------------

    if source_type == "file" and upload and upload.filename:
        original_name = Path(upload.filename).name
        extension = Path(original_name).suffix.lower()

        if extension not in {".csv", ".xlsx", ".xls"}:
            return jsonify({
                "success": False,
                "error": "Only CSV, XLS or XLSX files are supported.",
            }), 400

    elif source_type == "link" and source_url:
        if not source_url.startswith(("http://", "https://")):
            return jsonify({
                "success": False,
                "error": "Please provide a valid HTTP/HTTPS spreadsheet link.",
            }), 400

        original_name = "Imported Spreadsheet"
        extension = ""

    else:
        return jsonify({
            "success": False,
            "error": (
                "Choose a spreadsheet file."
                if source_type == "file"
                else "Provide a spreadsheet link."
            ),
        }), 400

    # -----------------------------------------------------
    # Processing mode and metadata
    # -----------------------------------------------------

    upload_mode = request.form.get(
        "upload_mode",
        "mixed",
    ).strip().lower()

    if upload_mode not in {"mixed", "single"}:
        upload_mode = "mixed"

    automatic_mode = upload_mode == "mixed"

    department = normalize_department(
        request.form.get("department", "")
    )

    reporting_period = normalize_reporting_period(
        request.form.get("reporting_period", "")
    )

    reporting_year = request.form.get(
        "reporting_year",
        ""
    ).strip()

    month = request.form.get(
        "reporting_month",
        ""
    ).strip()

    semester = request.form.get(
        "reporting_semester",
        ""
    ).strip()

    reporting_value = build_reporting_value(
        reporting_period,
        month,
        semester,
        reporting_year,
    )

    if not automatic_mode:
        if department not in DEPARTMENTS:
            return jsonify({
                "success": False,
                "error": "Please select a valid department/group.",
            }), 400

        if reporting_period not in REPORTING_PERIODS or not reporting_value:
            return jsonify({
                "success": False,
                "error": "Please select a valid reporting period, detail and year.",
            }), 400

    # Both modes use the normal automatic module classifier.
    target_module = None
    target_category = None

    # -----------------------------------------------------
    # Create temporary preview file
    # -----------------------------------------------------

    preview_dir = (
        Path(current_app.root_path)
        / "instance"
        / "preview_uploads"
    )
    preview_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    preview_token = secrets.token_urlsafe(24)

    if upload and upload.filename:
        suffix = extension
        preview_path = preview_dir / f"{preview_token}{suffix}"
        upload.save(preview_path)
        filename = original_name
    else:
        try:
            downloaded_path, downloaded_name = download_spreadsheet(
                source_url
            )
            downloaded_path = Path(downloaded_path)
            suffix = downloaded_path.suffix.lower()

            if suffix not in {".csv", ".xlsx", ".xls"}:
                downloaded_path.unlink(missing_ok=True)
                return jsonify({
                    "success": False,
                    "error": "The linked source is not a CSV, XLS or XLSX spreadsheet.",
                }), 400

            preview_path = preview_dir / f"{preview_token}{suffix}"

            # Windows may place the downloaded temporary file on C: while
            # the Flask project is on another drive (for example E:).
            # Path.replace() fails across drives with WinError 17.
            # shutil.move() handles cross-drive moves safely.
            shutil.move(
                str(downloaded_path),
                str(preview_path),
            )

            filename = downloaded_name or original_name

        except Exception as error:
            return jsonify({
                "success": False,
                "error": f"Unable to read the spreadsheet link: {error}",
            }), 400

    # -----------------------------------------------------
    # Read and classify without inserting anything
    # -----------------------------------------------------

    try:
        sheets = read_spreadsheet(
            str(preview_path),
            preview_path.suffix.lower(),
        )

        total_rows = 0
        max_columns = 0
        valid_metrics = 0
        unrecognized_metrics = 0
        missing_required_values = 0

        classification_counts = Counter()
        errors = []
        row_previews = []
        detected_departments = set()
        detected_years = set()
        detected_periods = set()
        detected_semesters = set()
        detected_months = set()

        metric_headers = {
            "description",
            "audit item",
            "audit_item",
            "item",
            "metric",
            "metric name",
            "metric_name",
            "indicator",
            "parameter",
            "submodule",
            "sub module",
            "sub-module",
        }

        for sheet_name, dataframe in sheets.items():
            if dataframe is None or is_documentation_sheet(sheet_name):
                continue

            dataframe = dataframe.dropna(how="all")

            if dataframe.empty:
                continue

            dataframe.columns = [
                str(column).strip()
                if str(column).strip()
                else f"Column_{index}"
                for index, column in enumerate(
                    dataframe.columns,
                    start=1,
                )
            ]

            max_columns = max(
                max_columns,
                len(dataframe.columns),
            )

            for row_number, (_, row) in enumerate(
                dataframe.iterrows(),
                start=2,
            ):

                row_dict = row.to_dict()

                if not any(
                    str(value).strip()
                    for value in row_dict.values()
                    if value is not None
                ):
                    continue

                total_rows += 1

                row_context = _detect_row_context(row)

                if automatic_mode:
                    row_department = row_context["department"]
                    row_year = row_context["year"]
                    row_period = row_context["period"]
                    row_detail = row_context["detail"]
                    row_reporting_value = row_context["reporting_value"]

                    if row_department:
                        detected_departments.add(row_department)
                    if row_year:
                        detected_years.add(row_year)
                    if row_period:
                        detected_periods.add(row_period)
                    if row_period == "Semester" and row_detail:
                        detected_semesters.add(row_detail)
                    if row_period == "Monthly" and row_detail:
                        detected_months.add(row_detail)
                else:
                    row_department = department
                    row_year = reporting_year
                    row_period = reporting_period
                    row_detail = semester if reporting_period == "Semester" else month if reporting_period == "Monthly" else ""
                    row_reporting_value = reporting_value

                normalized_row = {
                    normalize_text(key): value
                    for key, value in row_dict.items()
                }

                # For the Category/Sub Category spreadsheet format,
                # Sub Category is the actual metric name.  The old preview
                # only searched Description/Metric columns, so this workbook
                # incorrectly displayed "Missing" for every row.
                metric_text = ""

                subcategory_value = normalized_row.get(
                    normalize_text("sub category")
                )
                if subcategory_value is None:
                    subcategory_value = normalized_row.get(
                        normalize_text("subcategory")
                    )

                if subcategory_value is not None:
                    try:
                        if not pd_is_na(subcategory_value) and str(subcategory_value).strip():
                            metric_text = str(subcategory_value).strip()
                    except Exception:
                        if str(subcategory_value).strip():
                            metric_text = str(subcategory_value).strip()

                # Fallback for other spreadsheet formats.
                if not metric_text:
                    for header in metric_headers:
                        value = normalized_row.get(
                            normalize_text(header)
                        )
                        if value is None:
                            continue
                        try:
                            if pd_is_na(value):
                                continue
                        except Exception:
                            pass
                        if str(value).strip():
                            metric_text = str(value).strip()
                            break

                value_text = ""
                for value_header in (
                    "Value",
                    "Metric Value",
                    "Value / Count",
                    "Count",
                ):
                    candidate_value = normalized_row.get(normalize_text(value_header))
                    if candidate_value is None:
                        continue
                    try:
                        if pd_is_na(candidate_value):
                            continue
                    except Exception:
                        pass
                    if str(candidate_value).strip():
                        value_text = str(candidate_value).strip()
                        break

                classified_rows = classify_row(
                    row,
                    str(sheet_name),
                    upload_mode=upload_mode,
                    target_module=target_module,
                    target_category=target_category,
                )

                valid_matches = [
                    item
                    for item in classified_rows
                    if item[0] != "unclassified"
                    and item[1] != "unclassified"
                ]

                metadata_ok = row_context["valid"] if automatic_mode else True

                module_names = []
                if valid_matches:
                    seen_modules = set()
                    for module_key, category_key, _ in valid_matches:
                        if module_key in seen_modules:
                            continue
                        seen_modules.add(module_key)
                        module_name = MODULES.get(
                            module_key,
                            {},
                        ).get(
                            "name",
                            module_key,
                        )
                        module_names.append(module_name)

                    if metadata_ok:
                        valid_metrics += 1
                        for module_name in module_names:
                            classification_counts[module_name] += 1

                    else:
                        missing_required_values += 1
                        errors.append({
                            "sheet": str(sheet_name),
                            "row": row_number,
                            "type": "Missing row metadata",
                            "message": "Automatic Consolidation requires Department, Year and reporting Period for every row.",
                        })

                elif metric_text:
                    unrecognized_metrics += 1
                    errors.append({
                        "sheet": str(sheet_name),
                        "row": row_number,
                        "type": "Unrecognized metric",
                        "message": metric_text,
                    })

                else:
                    missing_required_values += 1
                    errors.append({
                        "sheet": str(sheet_name),
                        "row": row_number,
                        "type": "Missing required value",
                        "message": "Metric/description value is missing.",
                    })

                row_previews.append({
                    "row": row_number,
                    "department": row_department or "Missing",
                    "year": row_year or "Missing",
                    "period": row_period or "Missing",
                    "detail": row_detail or "-",
                    "metric": metric_text or "Missing",
                    "value": value_text or "Missing",
                    "module": ", ".join(module_names) if module_names else "Unclassified",
                })

        # Keep preview errors manageable even for very large workbooks.
        errors = errors[:100]

        return jsonify({
            "success": True,
            "preview_token": preview_token,
            "file_name": filename,
            "mode_label": "Automatic Consolidation" if automatic_mode else "Single Department / Period",
            "department": department if not automatic_mode else "",
            "reporting_period": reporting_period if not automatic_mode else "",
            "reporting_value": reporting_value if not automatic_mode else "",
            "reporting_year": reporting_year if not automatic_mode else "",
            "detected": {
                "departments": sorted(detected_departments),
                "years": sorted(detected_years),
                "periods": sorted(detected_periods),
                "semesters": sorted(detected_semesters),
                "months": sorted(detected_months),
                "mode_label": "Automatic Consolidation" if automatic_mode else "Single Department / Period",
            },
            "rows": row_previews[:100],
            "total_rows": total_rows,
            "valid_metrics": valid_metrics,
            "unrecognized_metrics": unrecognized_metrics,
            "missing_required_values": missing_required_values,
            "classification": dict(
                sorted(
                    classification_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ),
            "errors": errors,
        })

    except Exception as error:
        preview_path.unlink(missing_ok=True)
        return jsonify({
            "success": False,
            "error": f"Unable to preview the spreadsheet: {error}",
        }), 400


# =========================================================
# USER - SUBMIT DATA LINK
# =========================================================

@main_bp.route(
    "/submit-link",
    methods=["GET"]
)
@login_required
def submit_link():

    _cleanup_stale_preview_files()

    return render_template(
        "submit_link.html",
        modules=MODULES,
        departments=DEPARTMENTS,
        reporting_periods=REPORTING_PERIODS,
        months=MONTHS,
        semesters=SEMESTERS,
    )


# =========================================================
# USER - SUBMIT DATA LINK
# =========================================================

@main_bp.route(
    "/submit-link",
    methods=["POST"]
)
@login_required
def submit_link_post():
    """Confirm a previously previewed spreadsheet import."""

    _cleanup_stale_preview_files()

    preview_token = request.form.get(
        "preview_token",
        "",
    ).strip()

    source_url = request.form.get(
        "source_url",
        "",
    ).strip()

    upload = request.files.get(
        "spreadsheet_file"
    )

    source_type = request.form.get("source_type", "file").strip().lower()
    if source_type not in {"file", "link"}:
        source_type = "file"

    # -----------------------------------------------------
    # Resolve source file
    # -----------------------------------------------------

    preview_dir = (
        Path(current_app.root_path)
        / "instance"
        / "preview_uploads"
    )

    preview_path = None

    if preview_token:
        # Token is generated by the server, so only its exact filename
        # inside the preview directory is accepted.
        matches = list(
            preview_dir.glob(
                f"{preview_token}.*"
            )
        )

        if len(matches) != 1:
            flash(
                "Your preview has expired. Please preview the file again.",
                "warning",
            )
            return redirect(
                url_for("main.submit_link")
            )

        preview_path = matches[0]

    elif source_type == "file" and upload and upload.filename:
        extension = Path(
            upload.filename
        ).suffix.lower()

        if extension not in {".csv", ".xlsx", ".xls"}:
            flash(
                "Only CSV, XLS or XLSX files are supported.",
                "danger",
            )
            return redirect(
                url_for("main.submit_link")
            )

        preview_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_token = secrets.token_urlsafe(24)
        preview_path = preview_dir / f"{temporary_token}{extension}"
        upload.save(preview_path)

    elif source_type == "link" and source_url:
        if not source_url.startswith(("http://", "https://")):
            flash(
                "Please provide a valid HTTP/HTTPS spreadsheet link.",
                "danger",
            )
            return redirect(
                url_for("main.submit_link")
            )

        # Download it once and pass the local file to the existing importer.
        try:
            downloaded_path, _ = download_spreadsheet(
                source_url
            )
            preview_path = Path(
                downloaded_path
            )
        except Exception as error:
            flash(
                f"Unable to read the spreadsheet link: {error}",
                "danger",
            )
            return redirect(
                url_for("main.submit_link")
            )

    else:
        flash(
            "Please preview a spreadsheet before confirming the import.",
            "warning",
        )
        return redirect(
            url_for("main.submit_link")
        )

    # -----------------------------------------------------
    # Metadata validation
    # -----------------------------------------------------

    title = request.form.get(
        "title",
        "",
    ).strip() or "Imported Dataset"

    upload_mode = request.form.get(
        "upload_mode",
        "mixed",
    ).strip().lower()

    if upload_mode not in {"mixed", "single"}:
        upload_mode = "mixed"

    automatic_mode = upload_mode == "mixed"

    raw_department = request.form.get(
        "department",
        "",
    )

    department = normalize_department(
        raw_department
    )

    if not automatic_mode and department not in DEPARTMENTS:
        if preview_path and preview_token:
            preview_path.unlink(missing_ok=True)
        flash(
            "Please select a valid department/group.",
            "danger",
        )
        return redirect(
            url_for("main.submit_link")
        )

    if automatic_mode:
        department = None

    reporting_period = normalize_reporting_period(
        request.form.get(
            "reporting_period",
            "",
        )
    )

    reporting_year = request.form.get(
        "reporting_year",
        "",
    ).strip()

    month = request.form.get(
        "reporting_month",
        "",
    ).strip()

    semester = request.form.get(
        "reporting_semester",
        "",
    ).strip()

    reporting_value = build_reporting_value(
        reporting_period,
        month,
        semester,
        reporting_year,
    )

    if not automatic_mode and (
        reporting_period not in REPORTING_PERIODS
        or not reporting_value
    ):
        if preview_path and preview_token:
            preview_path.unlink(missing_ok=True)
        flash(
            "Please select a valid reporting period, detail and year.",
            "danger",
        )
        return redirect(
            url_for("main.submit_link")
        )

    if automatic_mode:
        reporting_period = None
        reporting_value = None
        reporting_year = None

    # Both UI modes use automatic module classification.
    target_module = None
    target_category = None

    user = get_current_user()

    # -----------------------------------------------------
    # Confirmed import
    # -----------------------------------------------------

    local_source = (
        f"local://{preview_path}"
        if preview_path
        else source_url
    )

    # Preserve the actual source classification before local preview handling
    # turns the source into a local:// path.
    if source_type == "file":
        suffix = Path(str(preview_path or source_url)).suffix.lower()
        source_type_for_metadata = (
            "excel" if suffix in {".xlsx", ".xls"}
            else "csv" if suffix == ".csv"
            else "other"
        )
    else:
        source_type_for_metadata = detect_source_type(source_url)

    upload_id, success, error = create_dataset(
        user["id"],
        title,
        local_source,
        upload_mode,
        target_module,
        target_category,
        department,
        None,
        reporting_period,
        reporting_value,
        "automatic" if automatic_mode else "single",
        "file" if source_type == "file" else "link",
        source_type_for_metadata,
    )

    # create_dataset consumes/deletes local files itself.

    if success:
        if error:
            flash(
                f"Import completed with warnings. Submission #{upload_id}. {error}",
                "warning",
            )
        else:
            flash(
                f"Data imported successfully. Submission #{upload_id}.",
                "success",
            )
    else:
        flash(
            f"Data import failed: {error}",
            "danger",
        )

    return redirect(
        url_for("main.home")
    )


# =========================================================
# COMPATIBILITY - SUBMIT DATASET
# =========================================================

@main_bp.route(
    "/submit-dataset",
    methods=["POST"]
)
@login_required
def submit_dataset():
    """Import data from a module page using either a file or a URL.

    Module pages are legacy entry points, so they now use the same two source
    choices as /submit-link: direct CSV/XLS/XLSX upload or spreadsheet URL.
    """
    _cleanup_stale_preview_files()

    source_type = request.form.get("source_type", "link").strip().lower()
    if source_type not in {"file", "link"}:
        source_type = "link"

    source_url = request.form.get("source_url", "").strip()
    upload = request.files.get("spreadsheet_file")
    title = request.form.get("title", "").strip() or "Module Dataset"

    module = (
        request.form.get("target_module")
        or request.form.get("module")
        or ""
    ).strip().lower()

    category = (
        request.form.get("target_category")
        or request.form.get("subtopic")
        or ""
    ).strip().lower()

    module = normalize_module(module)
    if module not in MODULES:
        flash("Invalid module selected.", "danger")
        return redirect(request.referrer or url_for("main.submit_link"))

    raw_department = request.form.get("department", "")
    department = normalize_department(raw_department)
    if department not in DEPARTMENTS:
        flash("Please select a valid department/group.", "danger")
        return redirect(request.referrer or url_for("main.submit_link"))

    reporting_period = normalize_reporting_period(
        request.form.get("reporting_period", "")
    )
    reporting_year = request.form.get("reporting_year", "").strip()
    reporting_month = request.form.get("reporting_month", "").strip()
    reporting_semester = request.form.get("reporting_semester", "").strip()
    reporting_value = request.form.get("reporting_value", "").strip()

    if reporting_period not in REPORTING_PERIODS:
        flash("Please select a valid reporting period.", "danger")
        return redirect(request.referrer or url_for("main.submit_link"))

    if not reporting_value:
        reporting_value = build_reporting_value(
            reporting_period,
            reporting_month,
            reporting_semester,
            reporting_year,
        )

    if not reporting_value:
        flash("Please complete the reporting period details and year.", "danger")
        return redirect(request.referrer or url_for("main.submit_link"))

    if category:
        category = normalize_category(category, module)
        if category not in MODULES[module]["categories"]:
            category = None

    preview_dir = (
        Path(current_app.root_path)
        / "instance"
        / "preview_uploads"
    )
    preview_dir.mkdir(parents=True, exist_ok=True)

    preview_path = None

    if source_type == "file":
        if not upload or not upload.filename:
            flash("Please choose a CSV, XLS or XLSX file.", "danger")
            return redirect(request.referrer or url_for("main.submit_link"))

        extension = Path(upload.filename).suffix.lower()
        if extension not in {".csv", ".xlsx", ".xls"}:
            flash("Only CSV, XLS or XLSX files are supported.", "danger")
            return redirect(request.referrer or url_for("main.submit_link"))

        token = secrets.token_urlsafe(24)
        preview_path = preview_dir / f"{token}{extension}"
        upload.save(preview_path)

    else:
        if not source_url.startswith(("http://", "https://")):
            flash("Please provide a valid HTTP/HTTPS spreadsheet link.", "danger")
            return redirect(request.referrer or url_for("main.submit_link"))

        try:
            downloaded_path, _ = download_spreadsheet(source_url)
            preview_path = Path(downloaded_path)
        except Exception as error:
            flash(f"Unable to read the spreadsheet link: {error}", "danger")
            return redirect(request.referrer or url_for("main.submit_link"))

    local_source = f"local://{preview_path}"

    user = get_current_user()

    upload_id, success, error = create_dataset(
        user["id"],
        title,
        local_source,
        "specific",
        module,
        category,
        department,
        None,
        reporting_period,
        reporting_value,
        "single",
        "file" if source_type == "file" else "link",
        (
            "excel" if Path(str(preview_path)).suffix.lower() in {".xlsx", ".xls"}
            else "csv" if Path(str(preview_path)).suffix.lower() == ".csv"
            else detect_source_type(source_url)
        ),
    )

    if success:
        message = f"Data imported successfully. Submission #{upload_id}."
        flash(message, "success")
    else:
        flash(f"Data import failed: {error}", "danger")

    return redirect(request.referrer or url_for("main.home"))


# =========================================================
# USER DASHBOARD
# =========================================================

# =========================================================
# MY DATA
# =========================================================

@main_bp.route("/my-data")
@login_required
def my_data():

    user = get_current_user()

    records = get_all_rows(
        user_id=user["id"]
    )

    columns = []

    for record in records:
        data = record.get("data", {})

        if not isinstance(data, dict):
            continue

        for column in data:
            if column not in columns:
                columns.append(column)

    return render_template(
        "admin_data.html",
        records=records,
        columns=columns,
        link_submissions=get_user_datasets(user["id"]),
        modules=MODULES,
        user_view=True,
    )


# ADD THE DELETE ROUTE HERE
@main_bp.route(
    "/my-data/<int:upload_id>/delete",
    methods=["POST"]
)
@login_required
def delete_my_upload(upload_id):

    from services.data_service import delete_user_upload

    user = get_current_user()

    try:
        deleted = delete_user_upload(
            upload_id,
            user["id"]
        )
    except Exception as error:
        flash(
            f"Delete failed: {error}",
            "danger"
        )
        return redirect(
            request.referrer
            or
            url_for("main.my_data")
        )

    if deleted:
        flash(
            "Your submission and its imported records were deleted.",
            "success"
        )
    else:
        flash(
            "Submission not found or you do not have permission to delete it.",
            "danger"
        )

    return redirect(
        url_for("main.my_data")
    )

# =========================================================
# ADMIN - OPEN SUBMISSION SOURCE
# =========================================================

@main_bp.route("/admin/submission/<int:upload_id>/open")
@login_required
def open_submission(upload_id):
    """Open the exact stored submission workbook in the browser.

    Administrators can open any submission.  Normal users can open only their
    own submissions.  The workbook is read from the permanently stored source
    file, never reconstructed from imported database rows.
    """
    connection = get_connection()
    try:
        upload = connection.execute(
            """
            SELECT
                u.*,
                users.name AS uploader_name,
                users.email AS uploader_email
            FROM uploads u
            LEFT JOIN users ON users.id=u.uploaded_by
            WHERE u.id=?
            LIMIT 1
            """,
            (upload_id,),
        ).fetchone()
    finally:
        connection.close()

    if not upload:
        flash("Submission not found.", "danger")
        return redirect(url_for("main.my_data"))

    current_user = get_current_user()
    if (
        current_user["role"] != "admin"
        and int(upload.get("uploaded_by") or 0) != int(current_user["id"])
    ):
        flash("You do not have permission to open this submission.", "danger")
        return redirect(url_for("main.my_data"))

    upload = dict(upload)
    original_path = str(upload.get("original_file_path") or "").strip()
    source_url = str(upload.get("source_url") or "").strip()

    # Prefer the permanently stored source file. This is the exact spreadsheet
    # submitted/imported by the user.
    resolved_original = resolve_submission_file(original_path)
    if resolved_original:
        file_path = resolved_original
    elif source_url.startswith(("http://", "https://")) and not source_url.startswith("https://local-upload.invalid/"):
        # Legacy link-only submissions can still open their original source.
        return redirect(source_url)
    else:
        file_path = None

    sheets = {}
    original_file = bool(file_path)

    try:
        import pandas as pd

        if file_path:
            extension = file_path.suffix.lower()
            if extension in {".xlsx", ".xls"}:
                sheets = pd.read_excel(file_path, sheet_name=None, dtype=object)
            elif extension == ".csv":
                sheets = {
                    "Imported Data": pd.read_csv(file_path, dtype=object)
                }
            else:
                raise ValueError("Unsupported spreadsheet format.")
        else:
            # Older imports created before permanent file storage still get a
            # useful browser view from the records already stored in SQLite.
            records = get_all_rows(upload_id=upload_id)
            if records:
                rows = []
                for record in records:
                    data = record.get("data") or {}
                    if isinstance(data, dict):
                        rows.append(dict(data))
                sheets = {"Imported Data": pd.DataFrame(rows)}

        if not sheets:
            flash("No spreadsheet data is available for this submission.", "warning")
            return redirect(url_for("main.my_data"))

        selected_sheet = request.args.get("sheet", "").strip()
        if selected_sheet not in sheets:
            selected_sheet = next(iter(sheets))

        dataframe = sheets[selected_sheet].copy()
        dataframe = dataframe.dropna(how="all")
        dataframe.columns = [str(column) for column in dataframe.columns]
        dataframe = dataframe.fillna("")

        page = max(request.args.get("page", 1, type=int), 1)
        per_page = 100
        total_rows = len(dataframe)
        total_pages = max((total_rows + per_page - 1) // per_page, 1)
        page = min(page, total_pages)
        start_row = (page - 1) * per_page
        end_row = min(start_row + per_page, total_rows)
        page_frame = dataframe.iloc[start_row:end_row]

        rows = []
        for values in page_frame.itertuples(index=False, name=None):
            rows.append([_preview_value(value) for value in values])

        departments = upload.get("department") or ""
        periods = upload.get("reporting_period") or ""

        if upload.get("upload_mode") == "mixed":
            metadata = get_all_datasets()
            current = next((item for item in metadata if int(item["id"]) == int(upload_id)), None)
            if current:
                departments = current.get("department_display") or departments or "Multiple / Row-level"
                periods = current.get("period_display") or periods or "Multiple / Row-level"

        return render_template(
            "submission_view.html",
            upload=upload,
            original_file=original_file,
            sheets=list(sheets.keys()),
            selected_sheet=selected_sheet,
            columns=list(dataframe.columns),
            rows=rows,
            page=page,
            total_pages=total_pages,
            total_rows=total_rows,
            start_row=start_row,
            end_row=end_row,
            departments=departments or "—",
            periods=periods or "—",
            imported_record_count=int(upload.get("imported_record_count") or 0),
        )

    except Exception as error:
        current_app.logger.exception("Unable to open submission %s: %s", upload_id, error)
        flash(f"Unable to open this submission: {error}", "danger")
        return redirect(url_for("main.admin"))


def _preview_value(value):
    if value is None:
        return ""
    try:
        if hasattr(value, "item"):
            value = value.item()
    except Exception:
        pass
    return str(value)


# =========================================================
# ADMIN HOME
# =========================================================

@main_bp.route("/admin")
@admin_required
def admin():

    uploads = get_all_datasets()

    report = get_report()

    department_summary = get_department_summary()

    # Keep user registration/activity information available on the
    # main admin dashboard as well as on /admin/users.
    user_analytics = get_user_analytics()


    return render_template(
        "admin.html",
        uploads=uploads,
        datasets=uploads,

        university_report=report,

        report=report,

        user_analytics=user_analytics,

        modules=MODULES,

        department_summary=department_summary,
        departments=DEPARTMENTS,
        reporting_periods=REPORTING_PERIODS,
    )


# =========================================================
# ADMIN USER ANALYTICS
# =========================================================

@main_bp.route("/admin/users/create", methods=["POST"])
@admin_required
def admin_create_user():
    """Create a normal user or another administrator.

    Only an authenticated administrator can reach this endpoint.
    """
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "user").strip().lower()

    if not name:
        flash("Please enter the user's full name.", "danger")
        return redirect(url_for("main.admin_users"))

    if not email:
        flash("Please enter the user's email address.", "danger")
        return redirect(url_for("main.admin_users"))

    if not password or len(password) < 6:
        flash("Password must contain at least 6 characters.", "danger")
        return redirect(url_for("main.admin_users"))

    if role not in ("user", "admin"):
        flash("Invalid account type selected.", "danger")
        return redirect(url_for("main.admin_users"))

    # Basic email validation.  The existing login system remains the source
    # of truth; this only prevents obviously malformed addresses.
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        flash("Please enter a valid email address.", "danger")
        return redirect(url_for("main.admin_users"))

    connection = None

    try:
        connection = get_connection()

        existing = connection.execute(
            """
            SELECT id
            FROM users
            WHERE email = ? COLLATE NOCASE
            LIMIT 1
            """,
            (email,),
        ).fetchone()

        if existing:
            flash("An account with this email already exists.", "danger")
            return redirect(url_for("main.admin_users"))

        # Use the same password hashing used by login.
        password_hash = generate_password_hash(password)

        # Keep account creation in the central DB helper so the users/admins
        # tables stay consistent.  The helper opens its own connection, so
        # close this read-only connection before calling it.
        connection.close()
        connection = None

        user_id = create_user(
            name=name,
            email=email,
            password_hash=password_hash,
            role=role,
        )

        account_label = "administrator" if role == "admin" else "user"
        flash(
            f"{account_label.capitalize()} account created successfully for {name}.",
            "success",
        )
        return redirect(url_for("main.admin_users"))

    except Exception as exc:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

        print("ADMIN CREATE USER ERROR:", repr(exc))
        flash(
            "Unable to create the account. The email may already be registered or the database may be unavailable.",
            "danger",
        )
        return redirect(url_for("main.admin_users"))


@main_bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    """Delete a user or administrator account from the admin portal."""
    current_user_id = session.get("user_id")

    if current_user_id == user_id:
        flash(
            "You cannot delete the administrator account you are currently using.",
            "danger",
        )
        return redirect(url_for("main.admin_users"))

    connection = None

    try:
        connection = get_connection()

        target = connection.execute(
            """
            SELECT id, name, email, role
            FROM users
            WHERE id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        if not target:
            flash("The account could not be found.", "danger")
            return redirect(url_for("main.admin_users"))

        target_role = str(target["role"] or "user").lower()

        # Never allow the application to end up without an administrator.
        if target_role == "admin":
            admin_count_row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM users
                WHERE LOWER(role) = 'admin'
                """
            ).fetchone()

            if int(admin_count_row["total"] or 0) <= 1:
                flash(
                    "The last administrator account cannot be deleted.",
                    "danger",
                )
                return redirect(url_for("main.admin_users"))

        # Preserve uploaded datasets, but remove their ownership from the
        # deleted account. Remove account-specific authentication records.
        connection.execute(
            "UPDATE uploads SET uploaded_by = NULL WHERE uploaded_by = ?",
            (user_id,),
        )

        connection.execute(
            "DELETE FROM login_activity WHERE user_id = ?",
            (user_id,),
        )

        try:
            connection.execute(
                "DELETE FROM password_reset_tokens WHERE user_id = ?",
                (user_id,),
            )
        except Exception:
            # Older databases may not have this table.
            pass

        connection.execute(
            "DELETE FROM admins WHERE user_id = ?",
            (user_id,),
        )

        connection.execute(
            "DELETE FROM users WHERE id = ?",
            (user_id,),
        )

        connection.commit()

        account_label = (
            "administrator"
            if target_role == "admin"
            else "user"
        )

        flash(
            f"{account_label.capitalize()} account for {target['name']} was deleted successfully.",
            "success",
        )

    except Exception as exc:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass

        print("ADMIN DELETE USER ERROR:", repr(exc))
        flash(
            "Unable to delete the account. No changes were made.",
            "danger",
        )

    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    return redirect(url_for("main.admin_users"))


@main_bp.route("/admin/users")
@admin_required
def admin_users():

    analytics = get_user_analytics()

    return render_template(
        "admin_users.html",
        **analytics,
    )


@main_bp.route("/admin/users.csv")
@admin_required
def admin_users_csv():

    analytics = get_user_analytics()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Full Name",
        "Email",
        "Account Type",
        "Registered",
        "Last Seen",
        "Status",
        "Access",
        "Submissions",
    ])

    for user in analytics["users"]:
        role = str(user.get("role", "user")).lower()
        is_admin = role == "admin"
        status = "ACTIVE" if user.get("is_active") else "INACTIVE"

        writer.writerow([
            user.get("name", ""),
            user.get("email", ""),
            "ADMIN" if is_admin else "USER",
            user.get("created_at", ""),
            user.get("last_seen_at", ""),
            status,
            "Full Access" if is_admin else "Standard Access",
            "" if is_admin else user.get("submission_count", 0),
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv",
    )
    response.headers[
        "Content-Disposition"
    ] = "attachment; filename=uce_user_report.csv"

    return response


# =========================================================
# ADMIN SETTINGS
# =========================================================

@main_bp.route("/admin/settings", methods=["GET"])
@admin_required
def admin_settings():
    return render_template(
        "admin_settings.html"
    )


@main_bp.route(
    "/admin/settings/generate-registration-code",
    methods=["POST"]
)
@admin_required
def generate_registration_code():
    try:
        registration_code = generate_admin_registration_code()

        return render_template(
            "admin_settings.html",
            registration_code=registration_code,
        )

    except Exception as error:
        print("ADMIN REGISTRATION CODE ERROR:", error)

        flash(
            "Unable to generate a new administrator registration code.",
            "danger"
        )

        return redirect(
            url_for("main.admin_settings")
        )


# =========================================================
# ADMIN DATA HELPERS
# =========================================================

# =========================================================
# ADMIN DATA HELPERS
# =========================================================

_RESERVED_DATA_FIELDS = {
    # Application classification fields. These are used internally by the
    # portal and must never be shown as imported university-data columns.
    "module",
    "module_key",
    "module_name",
    "module_no",
    "category",
    "category_key",
    "category_name",
    "submodule",
    "sub_module",
    "sub-module",
    "subtopic",
    "sub_topic",
    "topic",

    # Classification metadata that may exist in older imports or in
    # generated/test spreadsheets.
    "configured_category_key",
    "configured_target_header",
    "target_header",
    "configured_module",
    "configured_module_no",
    "configured_submodule",
    "configured_sub_module",
}


def _filter_admin_records(
    records,
    module=None,
    category=None,
    department=None,
    reporting_period=None,
):
    """
    Keep records strictly inside the requested department/module/submodule.
    Database queries already apply the same filters; this second pass protects
    the UI/report layer from accidentally mixing records.
    """

    filtered = []

    module = (module or "").strip().lower()
    category = (category or "").strip().lower()
    department = normalize_department(department) if department else ""
    reporting_period = normalize_reporting_period(reporting_period) if reporting_period else ""

    for record in records:

        record_module = str(
            record.get("module", "")
        ).strip().lower()

        record_category = str(
            record.get("category", "")
        ).strip().lower()

        # Automatic Consolidation stores Department and Period Type
        # inside each imported spreadsheet row. Single-department uploads
        # may still store them at upload level. Prefer row-level values and
        # fall back to upload-level metadata for older/single-mode records.
        row_data = record.get("data", {})
        if not isinstance(row_data, dict):
            row_data = {}

        def _row_value(*names):
            normalized_names = {
                str(name).strip().lower().replace(" ", "_").replace("-", "_")
                for name in names
            }
            for key, value in row_data.items():
                normalized_key = (
                    str(key).strip().lower()
                    .replace(" ", "_")
                    .replace("-", "_")
                )
                if normalized_key in normalized_names:
                    return value
            return ""

        row_department = _row_value(
            "Department", "Department Name", "Dept"
        )
        row_period = _row_value(
            "Period Type", "Reporting Period", "Period", "Frequency"
        )

        record_department = normalize_department(
            row_department or record.get("department", "")
        )

        record_period = normalize_reporting_period(
            row_period or record.get("reporting_period", "")
        )

        if module and record_module != module:
            continue

        if category and record_category != category:
            continue

        if department and record_department != department:
            continue

        if reporting_period and record_period != reporting_period:
            continue

        filtered.append(record)

    return filtered


def _clean_data_columns(records):
    """
    Return only actual imported spreadsheet columns.
    Module/category metadata is excluded.
    """

    columns = []

    for record in records:

        data = record.get(
            "data",
            {}
        )

        if not isinstance(data, dict):
            continue

        for column in data:

            normalized = str(
                column
            ).strip().lower()

            normalized = normalized.replace(
                " ",
                "_"
            )

            normalized = normalized.replace(
                "-",
                "_"
            )

            if normalized in _RESERVED_DATA_FIELDS:
                continue

            if column not in columns:
                columns.append(column)

    return columns


def _display_row(record, module_key, category_key):
    """
    Convert one database record into a clean display row.
    """

    data = record.get(
        "data",
        {}
    )

    if not isinstance(data, dict):
        data = {}

    module_info = MODULES[module_key]

    category_name = (
        module_info
        .get("categories", {})
        .get(
            category_key,
            category_key
        )
    )

    row = {
        "Record ID": record.get(
            "id",
            ""
        ),
    }

    for key, value in data.items():

        normalized = str(
            key
        ).strip().lower()

        normalized = normalized.replace(
            " ",
            "_"
        )

        normalized = normalized.replace(
            "-",
            "_"
        )

        if normalized in _RESERVED_DATA_FIELDS:
            continue

        row[key] = value

    return row


def _build_admin_module_report(
    module_key,
    records
):
    """
    Build a complete report for exactly one module.

    Every configured submodule is displayed separately.
    """

    module_info = MODULES[module_key]

    categories = {}

    all_rows = []

    for category_key, category_name in (
        module_info
        .get("categories", {})
        .items()
    ):

        category_records = _filter_admin_records(
            records,
            module=module_key,
            category=category_key
        )

        rows = [
            _display_row(
                record,
                module_key,
                category_key
            )
            for record in category_records
        ]

        columns = []

        for row in rows:

            for column in row:

                if column not in columns:
                    columns.append(column)

        categories[category_key] = {
            "name": category_name,
            "count": len(rows),
            "columns": columns,
            "rows": rows,
        }

        all_rows.extend(rows)

    numeric_totals = {}
    numeric_counts = {}

    for row in all_rows:

        for field, value in row.items():

            if field == "Record ID":
                continue

            try:

                number = float(
                    str(value)
                    .replace(",", "")
                    .replace("%", "")
                    .strip()
                )

            except (
                TypeError,
                ValueError
            ):
                continue

            numeric_totals[field] = (
                numeric_totals.get(
                    field,
                    0
                ) + number
            )

            numeric_counts[field] = (
                numeric_counts.get(
                    field,
                    0
                ) + 1
            )

    numeric_averages = {}

    for field in numeric_totals:

        count = numeric_counts.get(
            field,
            0
        )

        if count:

            numeric_averages[field] = round(
                numeric_totals[field] / count,
                2
            )

    return {
        "module_key": module_key,

        "module_name": module_info.get(
            "name",
            module_key
        ),

        "total_records": len(
            records
        ),

        "total_columns": (
            len(
                _clean_data_columns(
                    records
                )
            )
            if records
            else 0
        ),

        "categories": categories,

        "numeric_averages":
            numeric_averages,
    }


# =========================================================
# ADMIN - ALL DATA
# =========================================================

@main_bp.route(
    "/admin/data"
)
@admin_required
def admin_data():

    module = (
        request.args.get(
            "module",
            ""
        )
        .strip()
        .lower()
    )

    category = normalize_category(
        request.args.get("category", ""),
        module
    )

    raw_department = request.args.get("department", "")
    department = normalize_department(raw_department)

    reporting_period = normalize_reporting_period(
        request.args.get("period", "")
    )

    if raw_department.strip() and not is_valid_department(raw_department):
        flash("Invalid department/group selected.", "danger")
        return redirect(url_for("main.admin"))

    if reporting_period and reporting_period not in REPORTING_PERIODS:
        flash("Invalid reporting period selected.", "danger")
        return redirect(url_for("main.admin"))


    # -----------------------------------------------------
    # VALIDATE MODULE
    # -----------------------------------------------------

    if module and module not in MODULES:

        flash(
            "Invalid module selected.",
            "danger"
        )

        return redirect(
            url_for(
                "main.admin"
            )
        )

    # -----------------------------------------------------
    # VALIDATE SUBMODULE
    # -----------------------------------------------------

    if category:

        if not module:

            flash(
                "A module is required when selecting a submodule.",
                "danger"
            )

            return redirect(
                url_for(
                    "main.admin_data"
                )
            )

        if category not in (
            MODULES[module]
            .get(
                "categories",
                {}
            )
        ):

            flash(
                "Invalid submodule selected.",
                "danger"
            )

            return redirect(
                url_for(
                    "main.admin_data",
                    module=module
                )
            )

    # -----------------------------------------------------
    # GET DATABASE RECORDS
    # -----------------------------------------------------

    # The Admin landing page and department coverage page do not need raw
    # rows. Counts are calculated in SQL so large imports are not loaded into
    # the browser unnecessarily. A module/submodule page displays at most 50
    # rows per submodule.
    page_size = 50
    records = []
    total_records = 0
    category_counts = {}

    if module:
        if category:
            count_info = get_record_counts(
                module=module,
                category=category,
                department=department or None,
                reporting_period=reporting_period or None,
            )
            total_records = count_info["total"]
            category_counts = {category: count for category, count in count_info.get("by_category", {}).items()}
            records = get_all_rows(
                module=module,
                category=category,
                department=department or None,
                reporting_period=reporting_period or None,
                limit=page_size,
            )
        else:
            count_info = get_record_counts(
                module=module,
                department=department or None,
                reporting_period=reporting_period or None,
            )
            total_records = count_info["total"]
            category_counts = {category: count for category, count in count_info.get("by_category", {}).items()}

            categories = MODULES[module].get("categories", {})
            for category_key in categories:
                category_rows = get_all_rows(
                    module=module,
                    category=category_key,
                    department=department or None,
                    reporting_period=reporting_period or None,
                    limit=page_size,
                )
                records.extend(category_rows)
    elif department:
        count_info = get_record_counts(
            department=department or None,
            reporting_period=reporting_period or None,
        )
        total_records = count_info["total"]

    # -----------------------------------------------------
    # FIND COLUMNS
    # -----------------------------------------------------

    columns = _clean_data_columns(
        records
    )

    # -----------------------------------------------------
    # BUILD MODULE / SUBMODULE TABLES
    #
    # When a department is selected without a specific module, keep the
    # department filter and build the complete hierarchy:
    #
    # Department
    #   ↓
    # Module 01
    #   ↓
    # Submodule 01 / Submodule 02 / ...
    # Module 02
    #   ↓
    # ...
    #
    # This is intentionally built from the already department-filtered
    # `records` list, so CSE-1 can never display CSE-2/ECE/etc. records.
    # -----------------------------------------------------

    submodule_tables = []
    department_module_tables = []

    if module:

        categories = MODULES[module].get(
            "categories",
            {}
        )

        if category:

            categories_to_show = {
                category:
                    categories[category]
            }

        else:

            categories_to_show = categories

        for (
            category_key,
            category_name
        ) in categories_to_show.items():

            category_records = (
                _filter_admin_records(
                    records,
                    module=module,
                    category=category_key
                )
            )

            submodule_tables.append({

                "key":
                    category_key,

                "name":
                    category_name,

                "count":
                    category_counts.get(category_key, len(category_records)),

                "records":
                    category_records,

                "columns":
                    _clean_data_columns(
                        category_records
                    ),
            })

    elif department:

        count_info = get_record_counts(
            department=department,
            reporting_period=reporting_period or None,
        )

        for module_key, module_info in MODULES.items():
            module_count = count_info["by_module"].get(module_key, 0)
            module_categories = []

            for category_key, category_name in module_info.get(
                "categories", {}
            ).items():
                category_count = get_record_counts(
                    module=module_key,
                    category=category_key,
                    department=department,
                    reporting_period=reporting_period or None,
                )["total"]
                module_categories.append({
                    "key": category_key,
                    "name": category_name,
                    "count": category_count,
                    "records": [],
                    "columns": [],
                })

            department_module_tables.append({
                "key": module_key,
                "name": module_info.get("name", module_key),
                "description": module_info.get("description", ""),
                "icon": module_info.get("icon", "fa-folder"),
                "count": module_count,
                "categories": module_categories,
            })

    # -----------------------------------------------------
    # RENDER
    # -----------------------------------------------------

    return render_template(

        "admin_data.html",

        records=records,

        total_records=total_records,

        page_size=page_size,

        columns=columns,

        submodule_tables=
            submodule_tables,

        category_counts=
            category_counts,

        department_module_tables=
            department_module_tables,

        link_submissions=
            get_all_datasets(),

        modules=MODULES,

        selected_module=
            module,

        selected_category=
            category,

        selected_department=
            department,

        selected_period=
            reporting_period,

        department_summary=
            get_department_summary(),

        departments=
            DEPARTMENTS,

        reporting_periods=
            REPORTING_PERIODS,
    )


# =========================================================
# ADMIN - OVERALL / STANDARD REPORT
# =========================================================

@main_bp.route(
    "/admin/report"
)
@admin_required
def admin_report():

    selected_module = (
        request.args.get(
            "module",
            ""
        )
        .strip()
        .lower()
    )

    # -----------------------------------------------------
    # IF A MODULE WAS REQUESTED
    # -----------------------------------------------------

    if selected_module:

        if selected_module not in MODULES:

            flash(
                "Invalid module selected.",
                "danger"
            )

            return redirect(
                url_for(
                    "main.admin_report"
                )
            )

        return redirect(
            url_for(
                "main.admin_module_report",
                module=selected_module
            )
        )

    # -----------------------------------------------------
    # OVERALL UNIVERSITY REPORT
    # -----------------------------------------------------

    report = get_report()

    # -----------------------------------------------------
    # IMPORTANT FIX
    #
    # Your admin_report.html expects module_info.
    #
    # Previously it was NOT passed here.
    #
    # That caused:
    #
    # jinja2.exceptions.UndefinedError:
    # 'module_info' is undefined
    #
    # We provide a safe overall module_info object.
    # -----------------------------------------------------

    module_info = {

        "name":
            "All University Modules",

        "description":
            "Overall university data report.",

        "icon":
            "fa-chart-pie",

        "categories":
            {},
    }

    return render_template(

        "admin_report.html",

        report=report,

        modules=MODULES,

        overall=True,

        selected_module=None,

        module_info=module_info,
    )


# =========================================================
# ADMIN - MODULE REPORT
# =========================================================

@main_bp.route(
    "/admin/report/module/<module>"
)
@admin_required
def admin_module_report(module):

    module = (
        module
        or ""
    ).strip().lower()

    # -----------------------------------------------------
    # VALIDATE MODULE
    # -----------------------------------------------------

    if module not in MODULES:

        flash(
            "Module not found.",
            "danger"
        )

        return redirect(
            url_for(
                "main.admin"
            )
        )

    # -----------------------------------------------------
    # PRESERVE DEPARTMENT / REPORTING-PERIOD CONTEXT
    # -----------------------------------------------------

    raw_department = request.args.get("department", "")
    department = normalize_department(raw_department)
    reporting_period = normalize_reporting_period(
        request.args.get("period", "")
    )

    if raw_department.strip() and not is_valid_department(raw_department):
        flash("Invalid department selected.", "danger")
        return redirect(url_for("main.admin"))

    if reporting_period and reporting_period not in REPORTING_PERIODS:
        flash("Invalid reporting period selected.", "danger")
        return redirect(url_for("main.admin"))

    # Do not filter at upload level here. Automatic Consolidation stores
    # department/period per spreadsheet row; _filter_admin_records below
    # applies the correct row-level filter.
    records = get_all_rows(
        module=module
    )

    # -----------------------------------------------------
    # STRICT FILTER
    # -----------------------------------------------------

    records = _filter_admin_records(
        records,
        module=module,
        department=department or None,
        reporting_period=reporting_period or None,
    )

    # -----------------------------------------------------
    # BUILD REPORT
    # -----------------------------------------------------

    report = _build_admin_module_report(
        module,
        records
    )

    # -----------------------------------------------------
    # DATA COLUMNS
    # -----------------------------------------------------

    columns = _clean_data_columns(
        records
    )

    # -----------------------------------------------------
    # MODULE INFORMATION
    #
    # This is required by
    # admin_module_report.html.
    # -----------------------------------------------------

    module_info = MODULES[
        module
    ]

    # -----------------------------------------------------
    # RENDER
    # -----------------------------------------------------

    return render_template(

        "admin_module_report.html",

        module=module,

        module_key=module,

        module_info=module_info,

        report=report,

        records=records,

        columns=columns,

        selected_department=department,

        selected_period=reporting_period,

        modules=MODULES,
    )


# =========================================================
# ADMIN - CSV REPORT
# =========================================================

@main_bp.route(
    "/admin/report.csv"
)
@admin_required
def admin_report_csv():

    module = (
        request.args.get(
            "module",
            ""
        )
        .strip()
        .lower()
    )

    category = normalize_category(
        request.args.get("category", ""),
        module
    )

    raw_department = request.args.get("department", "")
    department = normalize_department(raw_department)
    reporting_period = normalize_reporting_period(
        request.args.get("period", "")
    )

    if raw_department.strip() and not is_valid_department(raw_department):
        return Response("Invalid department selected.", status=400, mimetype="text/plain")
    if reporting_period and reporting_period not in REPORTING_PERIODS:
        return Response("Invalid year selected.", status=400, mimetype="text/plain")

    # -----------------------------------------------------
    # VALIDATE MODULE
    # -----------------------------------------------------

    if module and module not in MODULES:

        return Response(
            "Invalid module selected.",
            status=400,
            mimetype="text/plain"
        )

    # -----------------------------------------------------
    # VALIDATE CATEGORY
    # -----------------------------------------------------

    if category:

        if not module:

            return Response(
                "A module is required for a submodule report.",
                status=400,
                mimetype="text/plain"
            )

        if category not in (
            MODULES[module]
            .get(
                "categories",
                {}
            )
        ):

            return Response(
                "Invalid submodule selected.",
                status=400,
                mimetype="text/plain"
            )

    # -----------------------------------------------------
    # GET EXACT RECORDS
    # -----------------------------------------------------

    # Fetch the module/category rows first. Department and period are
    # filtered below from the actual spreadsheet row, which is required
    # for Automatic Consolidation uploads.
    rows = get_all_rows(
        module=module or None,
        category=category or None,
    )

    # -----------------------------------------------------
    # STRICT FILTER
    # -----------------------------------------------------

    rows = _filter_admin_records(
        rows,
        module=module or None,
        category=category or None,
        department=department or None,
        reporting_period=reporting_period or None,
    )

    # -----------------------------------------------------
    # SORT BY SUBMODULE ORDER
    # -----------------------------------------------------

    if module:

        category_order = list(
            MODULES[module]
            .get(
                "categories",
                {}
            )
            .keys()
        )

        category_position = {

            key: index

            for index, key
            in enumerate(
                category_order
            )
        }

        rows.sort(

            key=lambda row: (

                category_position.get(
                    row.get(
                        "category",
                        ""
                    ),
                    9999
                ),

                str(
                    row.get(
                        "sheet_name",
                        ""
                    )
                ),

                int(
                    row.get(
                        "row_number",
                        0
                    )
                    or 0
                ),
            )
        )

    # -----------------------------------------------------
    # COLUMNS
    # -----------------------------------------------------

    columns = _clean_data_columns(
        rows
    )

    # -----------------------------------------------------
    # CSV
    # -----------------------------------------------------

    output = io.StringIO()

    fields = [

        "Record ID",

        "Dataset",

        "Uploader",

        "Sheet",

        "Row Number",

    ] + columns

    writer = csv.DictWriter(

        output,

        fieldnames=fields,

        extrasaction="ignore",
    )

    writer.writeheader()

    # -----------------------------------------------------
    # WRITE ROWS
    # -----------------------------------------------------

    for row in rows:

        row_module = row.get(
            "module",
            ""
        )

        row_category = row.get(
            "category",
            ""
        )

        record = {

            "Record ID":
                row.get(
                    "id",
                    ""
                ),

            "Dataset":
                row.get(
                    "title",
                    ""
                ),

            "Uploader":
                row.get(
                    "uploader_name",
                    ""
                ),

            "Sheet":
                row.get(
                    "sheet_name",
                    ""
                ),

            "Row Number":
                row.get(
                    "row_number",
                    ""
                ),
        }

        data = row.get(
            "data",
            {}
        )

        if isinstance(
            data,
            dict
        ):

            for key, value in data.items():

                normalized = str(
                    key
                ).strip().lower()

                normalized = normalized.replace(
                    " ",
                    "_"
                )

                normalized = normalized.replace(
                    "-",
                    "_"
                )

                if normalized in _RESERVED_DATA_FIELDS:
                    continue

                record[key] = value

        writer.writerow(
            record
        )

    # -----------------------------------------------------
    # FILE NAME
    # -----------------------------------------------------

    if category:

        filename = (
            f"uce_{module}_{category}_report.csv"
        )

    elif module:

        filename = (
            f"uce_{module}_report.csv"
        )

    else:

        filename = (
            "uce_university_report.csv"
        )

    # -----------------------------------------------------
    # DOWNLOAD
    # -----------------------------------------------------

    return Response(

        output.getvalue(),

        mimetype="text/csv; charset=utf-8",

        headers={
            "Content-Disposition":
                "attachment; filename=" +
                filename
        },
    )


# =========================================================
# ADMIN - PDF REPORT
# =========================================================

@main_bp.route(
    "/admin/report.pdf"
)
@admin_required
def admin_report_pdf():

    # -----------------------------------------------------
    # REPORTLAB
    # -----------------------------------------------------

    try:

        from reportlab.lib import colors

        from reportlab.lib.enums import (
            TA_CENTER
        )

        from reportlab.lib.pagesizes import (
            A4,
            landscape
        )

        from reportlab.lib.styles import (
            ParagraphStyle,
            getSampleStyleSheet
        )

        from reportlab.lib.units import mm

        from reportlab.platypus import (

            SimpleDocTemplate,

            Paragraph,

            Spacer,

            Table,

            TableStyle,

            PageBreak,
        )

    except ImportError:

        return Response(

            "ReportLab is not installed. "
            "Run: python -m pip install reportlab",

            status=500,

            mimetype="text/plain"
        )

    # -----------------------------------------------------
    # PARAMETERS
    # -----------------------------------------------------

    module = (
        request.args.get(
            "module",
            ""
        )
        .strip()
        .lower()
    )

    category = normalize_category(
        request.args.get("category", ""),
        module
    )

    raw_department = request.args.get("department", "")
    department = normalize_department(raw_department)
    reporting_period = normalize_reporting_period(
        request.args.get("period", "")
    )

    if raw_department.strip() and not is_valid_department(raw_department):
        return Response("Invalid department selected.", status=400, mimetype="text/plain")
    if reporting_period and reporting_period not in REPORTING_PERIODS:
        return Response("Invalid year selected.", status=400, mimetype="text/plain")

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    if module and module not in MODULES:

        return Response(
            "Invalid module selected.",
            status=400,
            mimetype="text/plain"
        )

    if category:

        if not module:

            return Response(
                "A module is required for a submodule report.",
                status=400,
                mimetype="text/plain"
            )

        if category not in (
            MODULES[module]
            .get(
                "categories",
                {}
            )
        ):

            return Response(
                "Invalid submodule selected.",
                status=400,
                mimetype="text/plain"
            )

    # -----------------------------------------------------
    # GET DATA
    # -----------------------------------------------------

    # Fetch the module/category rows first. Department and period are
    # filtered below from the actual spreadsheet row, which is required
    # for Automatic Consolidation uploads.
    rows = get_all_rows(
        module=module or None,
        category=category or None,
    )

    rows = _filter_admin_records(
        rows,
        module=module or None,
        category=category or None,
        department=department or None,
        reporting_period=reporting_period or None,
    )

    # -----------------------------------------------------
    # SORT
    # -----------------------------------------------------

    if module:

        category_order = list(
            MODULES[module]
            .get(
                "categories",
                {}
            )
            .keys()
        )

        category_position = {

            key: index

            for index, key
            in enumerate(
                category_order
            )
        }

        rows.sort(

            key=lambda row: (

                category_position.get(
                    row.get(
                        "category",
                        ""
                    ),
                    9999
                ),

                str(
                    row.get(
                        "sheet_name",
                        ""
                    )
                ),

                int(
                    row.get(
                        "row_number",
                        0
                    )
                    or 0
                ),
            )
        )

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    if module:

        module_name = MODULES[module].get(
            "name",
            module
        )

    else:

        module_name = (
            "All University Modules"
        )

    if department:
        module_name += f" — {department}"

    if reporting_period:
        module_name += f" — {reporting_period}"

    if category:

        title = (

            module_name
            + " - "
            + MODULES[module]
            ["categories"]
            [category]
        )

    else:

        title = module_name

    # -----------------------------------------------------
    # PDF BUFFER
    # -----------------------------------------------------

    buffer = io.BytesIO()

    document = SimpleDocTemplate(

        buffer,

        pagesize=landscape(A4),

        rightMargin=10 * mm,

        leftMargin=10 * mm,

        topMargin=12 * mm,

        bottomMargin=12 * mm,

        title=(
            "UCE Connect - "
            + title
        ),

        author="UCE Connect",
    )

    # -----------------------------------------------------
    # STYLES
    # -----------------------------------------------------

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(

        "UCEReportTitle",

        parent=styles["Title"],

        fontSize=22,

        leading=26,

        textColor=colors.HexColor(
            "#14213d"
        ),

        alignment=TA_CENTER,

        spaceAfter=8,
    )

    heading_style = ParagraphStyle(

        "UCEReportHeading",

        parent=styles["Heading2"],

        fontSize=14,

        leading=18,

        textColor=colors.HexColor(
            "#14213d"
        ),

        spaceBefore=8,

        spaceAfter=6,
    )

    cell_style = ParagraphStyle(

        "UCEReportCell",

        parent=styles["BodyText"],

        fontSize=7,

        leading=9,

        textColor=colors.HexColor(
            "#334155"
        ),
    )

    header_style = ParagraphStyle(

        "UCEReportHeader",

        parent=cell_style,

        fontSize=7,

        leading=9,

        textColor=colors.white,

        fontName="Helvetica-Bold",
    )

    # -----------------------------------------------------
    # STORY
    # -----------------------------------------------------

    story = [

        Paragraph(
            "UCE Connect",
            title_style
        ),

        Paragraph(
            title,
            heading_style
        ),

        Paragraph(
            f"Total records: {len(rows):,}",
            styles["Normal"]
        ),

        Spacer(
            1,
            8
        ),
    ]

    # -----------------------------------------------------
    # SAFE PDF TEXT
    # -----------------------------------------------------

    def paragraph_text(value):

        text = (
            ""
            if value is None
            else str(value)
        )

        return (
            text
            .replace(
                "&",
                "&amp;"
            )
            .replace(
                "<",
                "&lt;"
            )
            .replace(
                ">",
                "&gt;"
            )
        )

    # -----------------------------------------------------
    # BUILD TABLE
    # -----------------------------------------------------

    def build_table(
        table_rows,
        table_columns
    ):

        header = [

            Paragraph(
                paragraph_text(
                    column
                ),

                header_style
            )

            for column
            in table_columns
        ]

        data = [
            header
        ]

        for item in table_rows:

            data.append([

                Paragraph(

                    paragraph_text(
                        item.get(
                            column,
                            ""
                        )
                    ),

                    cell_style
                )

                for column
                in table_columns
            ])

        page_width = (
            landscape(A4)[0]
            - 20 * mm
        )

        fixed_width = 70 * mm

        data_width = max(

            45 * mm,

            page_width
            - fixed_width
        )

        extra_count = max(

            1,

            len(table_columns)
            - 4
        )

        extra_width = (
            data_width
            / extra_count
        )

        widths = []

        for column in table_columns:

            if column in {
                "Record ID",
                "Row Number"
            }:

                widths.append(
                    18 * mm
                )

            elif column in {
                "Module",
                "Sub-Module"
            }:

                widths.append(
                    28 * mm
                )

            else:

                widths.append(
                    extra_width
                )

        table = Table(

            data,

            repeatRows=1,

            colWidths=widths,

            hAlign="LEFT",
        )

        table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#14213d"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    colors.HexColor(
                        "#d9e0e8"
                    )
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP"
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                ),
            ])
        )

        return table

    # -----------------------------------------------------
    # EXACT SUBMODULE PDF
    # -----------------------------------------------------

    if category:

        category_name = (
            MODULES[module]
            ["categories"]
            [category]
        )

        category_rows = [

            row

            for row in rows

            if row.get(
                "category",
                ""
            ) == category
        ]

        columns = _clean_data_columns(
            category_rows
        )

        table_columns = [

            "Record ID",

            "Module",

            "Sub-Module",

        ] + columns

        display_rows = [

            _display_row(
                row,
                module,
                category
            )

            for row
            in category_rows
        ]

        story.append(

            Paragraph(

                f"Submodule: "
                f"{category_name} "
                f"({len(category_rows):,} records)",

                heading_style
            )
        )

        if display_rows:

            story.append(

                build_table(
                    display_rows,
                    table_columns
                )
            )

        else:

            story.append(

                Paragraph(
                    "No records have been imported for this submodule.",
                    styles["Normal"]
                )
            )

    # -----------------------------------------------------
    # MODULE PDF
    # -----------------------------------------------------

    elif module:

        module_info = MODULES[
            module
        ]

        for index, (
            category_key,
            category_name
        ) in enumerate(

            module_info
            .get(
                "categories",
                {}
            )
            .items()
        ):

            category_rows = [

                row

                for row in rows

                if row.get(
                    "category",
                    ""
                ) == category_key
            ]

            story.append(

                Paragraph(

                    f"{category_name} "
                    f"— "
                    f"{len(category_rows):,} records",

                    heading_style
                )
            )

            if category_rows:

                columns = _clean_data_columns(
                    category_rows
                )

                table_columns = [

                    "Record ID",

                    "Module",

                    "Sub-Module",

                ] + columns

                display_rows = [

                    _display_row(
                        row,
                        module,
                        category_key
                    )

                    for row
                    in category_rows
                ]

                story.append(

                    build_table(
                        display_rows,
                        table_columns
                    )
                )

            else:

                story.append(

                    Paragraph(

                        "No data available for this submodule.",

                        styles["Normal"]
                    )
                )

            if index < (
                len(
                    module_info
                    .get(
                        "categories",
                        {}
                    )
                ) - 1
            ):

                story.append(
                    Spacer(
                        1,
                        8
                    )
                )

    # -----------------------------------------------------
    # OVERALL UNIVERSITY PDF
    # -----------------------------------------------------

    else:

        overall_report = get_report()

        table_data = [[

            Paragraph(
                "Module",
                header_style
            ),

            Paragraph(
                "Sub-Module",
                header_style
            ),

            Paragraph(
                "Records",
                header_style
            ),
        ]]

        for module_item in (
            overall_report
            .get(
                "modules",
                []
            )
        ):

            for category_item in (
                module_item
                .get(
                    "categories",
                    []
                )
            ):

                table_data.append([

                    Paragraph(

                        paragraph_text(
                            module_item.get(
                                "name",
                                ""
                            )
                        ),

                        cell_style
                    ),

                    Paragraph(

                        paragraph_text(
                            category_item.get(
                                "name",
                                ""
                            )
                        ),

                        cell_style
                    ),

                    Paragraph(

                        paragraph_text(
                            category_item.get(
                                "count",
                                0
                            )
                        ),

                        cell_style
                    ),
                ])

        table = Table(

            table_data,

            repeatRows=1,

            colWidths=[
                65 * mm,
                170 * mm,
                25 * mm
            ],
        )

        table.setStyle(

            TableStyle([

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor(
                        "#14213d"
                    )
                ),

                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white
                ),

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.35,
                    colors.HexColor(
                        "#d9e0e8"
                    )
                ),

                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP"
                ),

                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5
                ),

                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                ),

                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    4
                ),
            ])
        )

        story.append(
            table
        )

    # -----------------------------------------------------
    # GENERATE PDF
    # -----------------------------------------------------

    document.build(
        story
    )

    buffer.seek(0)

    # -----------------------------------------------------
    # FILE NAME
    # -----------------------------------------------------

    if category:

        filename = (
            f"uce_{module}_{category}_report.pdf"
        )

    elif module:

        filename = (
            f"uce_{module}_report.pdf"
        )

    else:

        filename = (
            "uce_university_report.pdf"
        )

    # -----------------------------------------------------
    # DOWNLOAD
    # -----------------------------------------------------

    return send_file(

        buffer,

        mimetype="application/pdf",

        as_attachment=True,

        download_name=filename,
    )
# =========================================================
# ADMIN - FILE UPLOAD
#
# User portal uses links.
# This route is kept for compatibility.
# =========================================================

@main_bp.route(
    "/admin/upload",
    methods=["POST"]
)
@admin_required
def upload():

    flash(
        "Admin file upload is disabled. "
        "Users must submit spreadsheet links.",
        "warning"
    )


    return redirect(
        url_for(
            "main.admin"
        )
    )


# =========================================================
# ADMIN - DELETE UPLOAD
# =========================================================

@main_bp.route(
    "/admin/upload/<int:upload_id>/delete",
    methods=["POST"]
)
@admin_required
def remove_upload(upload_id):

    try:
        deleted = delete_upload(
            upload_id
        )
    except Exception as error:
        flash(
            f"Delete failed: {error}",
            "danger"
        )
        return redirect(
            request.referrer
            or
            url_for("main.admin")
        )


    if deleted:

        flash(
            "Submission and its imported records were deleted.",
            "success"
        )

    else:

        flash(
            "Submission not found.",
            "danger"
        )


    return redirect(
        request.referrer
        or
        url_for(
            "main.admin"
        )
    )


# =========================================================
# GENERIC MODULE ROUTE
#
# LOGIN REQUIRED
#
# This prevents users who are logged out from directly
# opening:
#
# /module/academics
# /module/placements
# etc.
#
# =========================================================

@main_bp.route(
    "/module/<module>"
)
@login_required
def module_page(module):

    module = (
        module
        or
        ""
    ).strip().lower()


    mapping = {

        "academics":
            "academics.index",

        "counselling":
            "counselling.index",

        "exams_evaluation":
            "exams_evaluation.index",

        "faculty_affairs":
            "faculty_affairs.index",

        "faculty_exchange":
            "faculty_exchange_abroad.index",

        "faculty_exchange_abroad":
            "faculty_exchange_abroad.index",

        "faculty_fdp_corporate":
            "faculty_fdp_corporate.index",

        "faculty_fdp_inhouse":
            "faculty_fdp_inhouse.index",

        "alumni":
            "extra_modules.alumni",

        "finance":
            "extra_modules.finance",

        "library":
            "library.library",

        "moocs":
            "moocs.index",

        "mous_international":
            "mous_international.index",

        "p_and_d":
            "p_and_d.index",

        "placements":
            "placements.index",

        "progression":
            "progression.index",

        "registrar_office":
            "registrar_office.index",

        "research":
            "research.index",

        "sac":
            "sac.index",

        "student_abroad_program":
            "student_abroad_program.index",

        "student_entrepreneurship":
            "student_entrepreneurship.index",

        "visiting_faculty":
            "visiting_faculty.index",

        "workload_of_students":
            "workload_of_students.index",
    }


    endpoint = mapping.get(
        module
    )


    if not endpoint:

        flash(
            "Module not found.",
            "danger"
        )

        return redirect(
            url_for(
                "main.home"
            )
        )


    return redirect(
        url_for(
            endpoint
        )
    )


# =========================================================
# API DATA
#
# LOGIN REQUIRED
#
# This is IMPORTANT.
#
# Without @login_required, someone who logs out could
# still request:
#
# /api/data/academics/syllabus
#
# and receive database data.
#
# =========================================================

@main_bp.route(
    "/api/data/<module>/<subtopic>"
)
@login_required
def api_data(
    module,
    subtopic
):

    module = (
        module
        or
        ""
    ).strip().lower()


    subtopic = normalize_category(
        subtopic,
        module
    )


    if module not in MODULES:

        return Response(

            '{"success":false,"error":"Unknown module."}',

            status=404,

            mimetype="application/json",
        )


    # -----------------------------------------------------
    # Get module data
    # -----------------------------------------------------

    grouped_data = get_module_data(
        module
    )


    items = grouped_data.get(
        subtopic,
        []
    )


    # -----------------------------------------------------
    # No data
    # -----------------------------------------------------

    if not items:

        return Response(

            __import__("json").dumps(

                {

                    "success": True,

                    "uploaded": False,

                    "module": module,

                    "subtopic": subtopic,

                    "title":
                        MODULES[module]
                        ["categories"]
                        .get(
                            subtopic,
                            subtopic
                        ),

                    "data": [],

                    "analysis": {

                        "rows": 0,

                        "columns": 0,

                    },

                }

            ),

            mimetype="application/json",
        )


    # -----------------------------------------------------
    # Convert database items to API rows
    # -----------------------------------------------------

    rows = []


    for item in items:

        data = item.get(
            "data",
            {}
        )


        if isinstance(
            data,
            dict
        ):

            rows.append(
                data
            )


    # -----------------------------------------------------
    # Columns
    # -----------------------------------------------------

    columns = []


    for row in rows:

        for column in row:

            if column not in columns:

                columns.append(
                    column
                )


    # -----------------------------------------------------
    # Basic numeric analysis
    # -----------------------------------------------------

    numeric_values = []


    for row in rows:

        for value in row.values():

            try:

                number = float(value)

                numeric_values.append(
                    number
                )

            except (
                TypeError,
                ValueError
            ):

                pass


    analysis = {

        "rows":
            len(rows),

        "columns":
            len(columns),

        "average":
            (
                round(
                    sum(numeric_values)
                    /
                    len(numeric_values),
                    2
                )
                if numeric_values
                else None
            ),

        "minimum":
            (
                min(numeric_values)
                if numeric_values
                else None
            ),

        "maximum":
            (
                max(numeric_values)
                if numeric_values
                else None
            ),
    }


    # -----------------------------------------------------
    # Return JSON
    # -----------------------------------------------------

    import json


    return Response(

        json.dumps(

            {

                "success": True,

                "uploaded": True,

                "module": module,

                "subtopic": subtopic,

                "title":
                    MODULES[module]
                    ["categories"]
                    .get(
                        subtopic,
                        subtopic
                    ),

                "file_name":
                    "Uploaded Dataset",

                "uploaded_at":
                    (
                        items[0]
                        .get(
                            "created_at"
                        )
                        if items
                        else ""
                    ),

                "data":
                    rows,

                "analysis":
                    analysis,

            },

            default=str,

        ),

        mimetype="application/json",
    )

# =========================================================
# 404 - PAGE NOT FOUND
# =========================================================

@main_bp.app_errorhandler(404)
def page_not_found(error):
    return render_template(
        "404.html"
    ), 404


# =========================================================
# 413 - FILE TOO LARGE
# =========================================================

@main_bp.app_errorhandler(413)
def file_too_large(error):

    flash(
        "Uploaded file is too large.",
        "danger"
    )

    return redirect(
        url_for(
            "main.admin"
        )
    )
