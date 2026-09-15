import csv
import io
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

@main_bp.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "GET":

        return render_template(
            "register.html"
        )


    name = request.form.get(
        "name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    confirm_password = request.form.get(
        "confirm_password",
        ""
    )

    role = request.form.get(
        "role",
        "user"
    ).strip().lower()

    admin_code = request.form.get(
        "admin_code",
        ""
    ).strip()


    if not name or not email:

        flash(
            "Name and email are required.",
            "danger"
        )

        return render_template(
            "register.html"
        )


    if len(password) < 8:

        flash(
            "Password must contain at least 8 characters.",
            "danger"
        )

        return render_template(
            "register.html"
        )


    if password != confirm_password:

        flash(
            "Passwords do not match.",
            "danger"
        )

        return render_template(
            "register.html"
        )


    if role not in (
        "user",
        "admin"
    ):

        role = "user"


    if (
        role == "admin"
        and admin_code != Config.ADMIN_REGISTRATION_CODE
    ):

        flash(
            "Invalid administrator registration code.",
            "danger"
        )

        return render_template(
            "register.html"
        )


    connection = get_connection()

    try:

        existing = connection.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            COLLATE NOCASE
            LIMIT 1
            """,
            (email,),
        ).fetchone()


        if existing:

            flash(
                "An account with this email already exists.",
                "danger"
            )

            return render_template(
                "register.html"
            )


        cursor = connection.execute(
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
                generate_password_hash(password),
                role,
            ),
        )


        connection.commit()


        session.clear()

        session["user_id"] = cursor.lastrowid

        session["user_name"] = name

        session["user_role"] = role


        flash(
            "Registration successful.",
            "success"
        )


        if role == "admin":

            return redirect(
                url_for(
                    "main.admin"
                )
            )


        return redirect(
            url_for(
                "main.submit_link"
            )
        )


    except Exception as error:

        connection.rollback()

        flash(
            f"Registration failed: {error}",
            "danger"
        )

        return render_template(
            "register.html"
        )

    finally:

        connection.close()


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


    target_module = request.form.get(
        "target_module"
    )

    target_category = request.form.get(
        "target_category"
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


    # Compatibility aliases

    module = {
        "faculty_exchange_abroad":
            "faculty_exchange",

        "placementa":
            "placements",

    }.get(
        module,
        module
    )


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

@main_bp.route("/dashboard")
@login_required
def user_dashboard():

    user = get_current_user()


    return render_template(
        "user_dashboard.html",
        uploads=get_user_datasets(
            user["id"]
        ),
        modules=MODULES,
    )


# =========================================================
# MY DATA
# =========================================================

@main_bp.route("/my-data")
@login_required
def my_data():

    user = get_current_user()


    records = [
        record
        for record in get_all_rows()
        if record.get(
            "uploaded_by"
        ) == user["id"]
    ]


    columns = []


    for record in records:

        data = record.get(
            "data",
            {}
        )


        if not isinstance(
            data,
            dict
        ):

            continue


        for column in data:

            if column not in columns:

                columns.append(
                    column
                )


    return render_template(
        "admin_data.html",
        records=records,
        columns=columns,
        link_submissions=get_user_datasets(
            user["id"]
        ),
        modules=MODULES,
        user_view=True,
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
# ADMIN - ALL DATA
# =========================================================

@main_bp.route("/admin/data")
@admin_required
def admin_data():

    module = request.args.get(
        "module",
        ""
    ).strip()


    category = request.args.get(
        "category",
        ""
    ).strip()


    records = get_all_rows(
        module=module or None,
        category=category or None,
    )


    columns = []


    for record in records:

        data = record.get(
            "data",
            {}
        )


        if not isinstance(
            data,
            dict
        ):

            continue


        for column in data:

            if column not in columns:

                columns.append(
                    column
                )


    return render_template(
        "admin_data.html",

        records=records,

        columns=columns,

        link_submissions=get_all_datasets(),

        modules=MODULES,

        selected_module=module,

        selected_category=category,
    )


# =========================================================
# ADMIN - OVERALL REPORT
# =========================================================

@main_bp.route(
    "/admin/report"
)
@admin_required
def admin_report():

    report = get_report()


    return render_template(
        "admin_report.html",

        report=report,

        modules=MODULES,
    )


# =========================================================
# ADMIN - MODULE REPORT
#
# IMPORTANT:
#
# Route uses <module>, NOT <module_key>
#
# This matches:
#
# url_for(
#     'main.admin_module_report',
#     module=module.key
# )
#
# =========================================================

@main_bp.route(
    "/admin/report/module/<module>"
)
@admin_required
def admin_module_report(module):

    module = (
        module
        or
        ""
    ).strip().lower()


    # -----------------------------------------------------
    # Validate module
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
    # Get all records for this module
    # -----------------------------------------------------

    records = get_all_rows(
        module=module
    )


    # -----------------------------------------------------
    # Get grouped module data
    # -----------------------------------------------------

    grouped_data = get_module_data(
        module
    )


    # -----------------------------------------------------
    # Build module report
    # -----------------------------------------------------

    report = build_module_report(
        module,
        grouped_data
    )


    # -----------------------------------------------------
    # Collect every column
    # -----------------------------------------------------

    columns = []


    for row in records:

        data = row.get(
            "data",
            {}
        )


        if not isinstance(
            data,
            dict
        ):

            continue


        for column in data:

            if column not in columns:

                columns.append(
                    column
                )


    # -----------------------------------------------------
    # Module information
    # -----------------------------------------------------

    module_info = MODULES[
        module
    ]


    # -----------------------------------------------------
    # Render report
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

    module = request.args.get(
        "module",
        ""
    ).strip()


    category = request.args.get(
        "category",
        ""
    ).strip()


    rows = get_all_rows(
        module=module or None,
        category=category or None,
    )


    columns = []


    for row in rows:

        data = row.get(
            "data",
            {}
        )


        if not isinstance(
            data,
            dict
        ):

            continue


        for column in data:

            if column not in columns:

                columns.append(
                    column
                )


    output = io.StringIO()


    fields = [

        "Dataset",

        "Uploader",

        "Module",

        "Category",

        "Sheet",

        "Row Number",

    ] + columns


    writer = csv.DictWriter(

        output,

        fieldnames=fields,

        extrasaction="ignore",
    )


    writer.writeheader()


    for row in rows:

        record = {

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

            "Module":
                row.get(
                    "module",
                    ""
                ),

            "Category":
                row.get(
                    "category",
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

            record.update(
                data
            )


        writer.writerow(
            record
        )


    return Response(

        output.getvalue(),

        mimetype="text/csv",

        headers={

            "Content-Disposition":
                "attachment; "
                "filename=uce_report.csv"

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

    try:

        from reportlab.lib import colors

        from reportlab.lib.pagesizes import A4

        from reportlab.lib.styles import (
            getSampleStyleSheet
        )

        from reportlab.platypus import (

            SimpleDocTemplate,

            Paragraph,

            Spacer,

            Table,

            TableStyle,

        )

    except ImportError:

        return Response(

            "ReportLab is not installed. "
            "Run: python -m pip install reportlab",

            status=500,

            mimetype="text/plain",
        )


    report = get_report()


    buffer = io.BytesIO()


    document = SimpleDocTemplate(

        buffer,

        pagesize=A4,

        rightMargin=30,

        leftMargin=30,

        topMargin=30,

        bottomMargin=30,
    )


    styles = getSampleStyleSheet()


    story = [

        Paragraph(
            "UCE Connect - University Data Report",
            styles["Title"]
        ),

        Spacer(
            1,
            12
        ),

        Paragraph(

            f"Total records: "
            f"{report['total_records']}",

            styles["Normal"]
        ),

        Paragraph(

            f"Total submissions: "
            f"{report['total_uploads']}",

            styles["Normal"]
        ),

        Spacer(
            1,
            15
        ),
    ]


    data = [

        [
            "Module",
            "Records",
            "Active Categories"
        ]

    ]


    for module in report["modules"]:

        active = sum(

            1

            for category
            in module["categories"]

            if category["count"] > 0

        )


        data.append(

            [

                module["name"],

                str(
                    module["total_records"]
                ),

                str(active),

            ]

        )


    table = Table(

        data,

        repeatRows=1
    )


    table.setStyle(

        TableStyle(

            [

                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey
                ),

                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.lightgrey
                ),

                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold"
                ),

            ]

        )

    )


    story.append(
        table
    )


    document.build(
        story
    )


    buffer.seek(0)


    return send_file(

        buffer,

        mimetype="application/pdf",

        as_attachment=True,

        download_name=
            "uce_university_report.pdf",
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

    deleted = delete_upload(
        upload_id
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

        "library":
            "library.index",

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


    subtopic = (
        subtopic
        or
        ""
    ).strip()


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
# 404
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