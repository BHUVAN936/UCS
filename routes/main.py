import csv
import io
import hashlib
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    send_file,
)

from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from config import Config
from database.db import get_connection
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
    get_report,
    get_user_datasets,
    get_module_data,
    build_module_report,
    normalize_module,
    normalize_category,
)


main_bp = Blueprint(
    "main",
    __name__
)


# =========================================================
# AUTHENTICATION
# =========================================================

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
# REGISTER
# =========================================================

@main_bp.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "user").strip().lower()
        terms = request.form.get("terms")
        registration_code = request.form.get(
            "registration_code", ""
        ).strip()

        # =====================================================
        # BASIC VALIDATION
        # =====================================================

        if not name:
            flash("Please enter your full name.", "danger")
            return redirect(url_for("main.register"))

        if not email:
            flash("Please enter your email address.", "danger")
            return redirect(url_for("main.register"))

        if not password:
            flash("Please enter a password.", "danger")
            return redirect(url_for("main.register"))

        if len(password) < 6:
            flash(
                "Password must contain at least 6 characters.",
                "danger"
            )
            return redirect(url_for("main.register"))

        if password != confirm_password:
            flash(
                "Passwords do not match.",
                "danger"
            )
            return redirect(url_for("main.register"))

        if not terms:
            flash(
                "Please accept the terms before creating your account.",
                "danger"
            )
            return redirect(url_for("main.register"))

        # =====================================================
        # ROLE VALIDATION
        # =====================================================

        if role not in ("user", "admin"):
            flash(
                "Invalid account type selected.",
                "danger"
            )
            return redirect(url_for("main.register"))

        # =====================================================
        # ADMIN CODE VALIDATION
        # =====================================================

        if role == "admin":

            if not registration_code:
                flash(
                    "Admin registration code is required.",
                    "danger"
                )
                return redirect(url_for("main.register"))

            if not verify_admin_registration_code(registration_code):
                flash(
                    "Invalid administrator registration code.",
                    "danger"
                )
                return redirect(url_for("main.register"))

        # =====================================================
        # DATABASE
        # =====================================================

        connection = None

        try:

            # -------------------------------------------------
            # USE THE SAME DATABASE CONNECTION AS LOGIN/AUTH
            # -------------------------------------------------

            connection = get_connection()

            # -------------------------------------------------
            # CHECK EXISTING EMAIL
            # -------------------------------------------------

            existing_user = connection.execute(
                """
                SELECT id
                FROM users
                WHERE email = ?
                COLLATE NOCASE
                LIMIT 1
                """,
                (email,)
            ).fetchone()

            if existing_user:

                flash(
                    "An account with this email already exists.",
                    "danger"
                )

                return redirect(
                    url_for("main.register")
                )

            # -------------------------------------------------
            # HASH PASSWORD
            # -------------------------------------------------

            password_hash = generate_password_hash(
                password
            )

            # -------------------------------------------------
            # CREATE USER
            # -------------------------------------------------

            connection.execute(
                """
                INSERT INTO users
                (
                    name,
                    email,
                    password_hash,
                    role
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    password_hash,
                    role
                )
            )

            connection.commit()

            flash(
                "Account created successfully. Please sign in.",
                "success"
            )

            return redirect(
                url_for("main.login")
            )

        except Exception as e:

            if connection is not None:

                try:
                    connection.rollback()
                except Exception:
                    pass

            print(
                "REGISTRATION ERROR:",
                repr(e)
            )

            flash(
                "Unable to create account. Please try again.",
                "danger"
            )

            return redirect(
                url_for("main.register")
            )

        finally:

            if connection is not None:

                try:
                    connection.close()
                except Exception:
                    pass

    return render_template("register.html")


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

        flash(
            "Invalid email or password.",
            "danger"
        )

        return render_template(
            "login.html"
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
# USER - SUBMIT DATA LINK
# =========================================================

@main_bp.route(
    "/submit-link",
    methods=["GET"]
)
@login_required
def submit_link():

    return render_template(
        "submit_link.html",
        modules=MODULES,
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

    source_url = request.form.get(
        "source_url",
        ""
    ).strip()

    title = request.form.get(
        "title",
        ""
    ).strip()

    if not title:

        title = "Imported Dataset"


    upload_mode = request.form.get(
        "upload_mode",
        "mixed"
    ).strip().lower()


    target_module = normalize_module(
        request.form.get("target_module", "")
    )
    target_category = normalize_category(
        request.form.get("target_category", ""),
        target_module
    )


    if not source_url.startswith(
        (
            "http://",
            "https://"
        )
    ):

        flash(
            "Please provide a valid HTTP/HTTPS spreadsheet link.",
            "danger"
        )

        return redirect(
            url_for(
                "main.submit_link"
            )
        )


    user = get_current_user()


    upload_id, success, error = create_dataset(
        user["id"],
        title,
        source_url,
        upload_mode,
        target_module,
        target_category,
    )


    if success:

        flash(
            f"Data imported successfully. Submission #{upload_id}.",
            "success"
        )

    else:

        flash(
            f"Data import failed: {error}",
            "danger"
        )


    return redirect(
        url_for(
            "main.home"
        )
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

    source_url = request.form.get(
        "source_url",
        ""
    ).strip()

    title = request.form.get(
        "title",
        ""
    ).strip()


    if not title:

        title = "Module Dataset"


    module = (
        request.form.get(
            "target_module"
        )
        or
        request.form.get(
            "module"
        )
        or
        ""
    )


    category = (
        request.form.get(
            "target_category"
        )
        or
        request.form.get(
            "subtopic"
        )
        or
        ""
    )


    module = module.strip().lower()

    category = category.strip().lower()


    # Use the single centralized module alias map.
    module = normalize_module(module)


    if module not in MODULES:

        flash(
            "Invalid module selected.",
            "danger"
        )

        return redirect(
            request.referrer
            or
            url_for(
                "main.submit_link"
            )
        )


    if not source_url.startswith(
        (
            "http://",
            "https://"
        )
    ):

        flash(
            "Please provide a valid HTTP/HTTPS spreadsheet link.",
            "danger"
        )

        return redirect(
            request.referrer
            or
            url_for(
                "main.submit_link"
            )
        )


    user = get_current_user()


    upload_id, success, error = create_dataset(
        user["id"],
        title,
        source_url,
        "specific",
        module,
        category,
    )


    if success:

        flash(
            f"Data imported successfully. Submission #{upload_id}.",
            "success"
        )

    else:

        flash(
            f"Data import failed: {error}",
            "danger"
        )


    return redirect(
        request.referrer
        or
        url_for(
            "main.home"
        )
    )


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
# ADMIN HOME
# =========================================================

@main_bp.route("/admin")
@admin_required
def admin():

    uploads = get_all_datasets()

    report = get_report()


    return render_template(
        "admin.html",
        uploads=uploads,
        datasets=uploads,

        university_report=report,

        report=report,

        modules=MODULES,
    )


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


def _filter_admin_records(records, module=None, category=None):
    """
    Keep records strictly inside the requested module/category.
    This prevents records belonging to other modules from appearing.
    """

    filtered = []

    module = (module or "").strip().lower()
    category = (category or "").strip().lower()

    for record in records:

        record_module = str(
            record.get("module", "")
        ).strip().lower()

        record_category = str(
            record.get("category", "")
        ).strip().lower()

        if module and record_module != module:
            continue

        if category and record_category != category:
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

        "total_columns": len(
            _clean_data_columns(
                records
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

    records = get_all_rows(
        module=module or None,
        category=category or None
    )

    # -----------------------------------------------------
    # STRICT FILTER
    # -----------------------------------------------------

    records = _filter_admin_records(
        records,
        module=module or None,
        category=category or None
    )

    # -----------------------------------------------------
    # FIND COLUMNS
    # -----------------------------------------------------

    columns = _clean_data_columns(
        records
    )

    # -----------------------------------------------------
    # BUILD SUBMODULE TABLES
    #
    # This is important:
    #
    # Module
    #   ↓
    # Submodule 1 → its records
    # Submodule 2 → its records
    # Submodule 3 → its records
    #
    # Records from another submodule are NOT mixed.
    # -----------------------------------------------------

    submodule_tables = []

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
                    len(category_records),

                "records":
                    category_records,

                "columns":
                    _clean_data_columns(
                        category_records
                    ),
            })

    # -----------------------------------------------------
    # RENDER
    # -----------------------------------------------------

    return render_template(

        "admin_data.html",

        records=records,

        columns=columns,

        submodule_tables=
            submodule_tables,

        link_submissions=
            get_all_datasets(),

        modules=MODULES,

        selected_module=
            module,

        selected_category=
            category,
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
    # GET ONLY THIS MODULE
    # -----------------------------------------------------

    records = get_all_rows(
        module=module
    )

    # -----------------------------------------------------
    # STRICT FILTER
    # -----------------------------------------------------

    records = _filter_admin_records(
        records,
        module=module
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

    rows = get_all_rows(
        module=module or None,
        category=category or None
    )

    # -----------------------------------------------------
    # STRICT FILTER
    # -----------------------------------------------------

    rows = _filter_admin_records(
        rows,
        module=module or None,
        category=category or None
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

    rows = get_all_rows(
        module=module or None,
        category=category or None
    )

    rows = _filter_admin_records(
        rows,
        module=module or None,
        category=category or None
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
