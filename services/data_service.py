import io
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from database.db import get_connection
from services.link_service import download_spreadsheet


MODULES = {
    "academics": {"name": "Academics", "icon": "fa-book-open", "description": "Courses, syllabus, curriculum and academic attainment.", "categories": {"syllabus_revision": "Syllabus Revision", "new_courses": "New Courses Introduced", "value_added_courses": "Value-Added Courses", "co_attainment": "CO Attainment", "po_attainment": "PO Attainment"}},
    "counselling": {"name": "Counselling", "icon": "fa-comments", "description": "Student, mental-health and career counselling.", "categories": {"student_counselling": "Student Counselling", "mental_health": "Mental Health", "career_counselling": "Career Counselling"}},
    "exams_evaluation": {"name": "Exams Evaluation", "icon": "fa-file-circle-check", "description": "Examinations, evaluation and results.", "categories": {"examinations": "Examinations", "evaluation": "Evaluation", "results": "Results"}},
    "faculty_affairs": {"name": "Faculty Affairs", "icon": "fa-user-tie", "description": "Faculty information and development.", "categories": {"faculty": "Faculty Information", "development": "Faculty Development"}},
    "faculty_exchange_abroad": {"name": "Faculty Exchange Abroad", "icon": "fa-plane", "description": "Faculty exchange and international activities.", "categories": {"exchange": "Faculty Exchange", "international": "International Faculty"}},
    "faculty_fdp_corporate": {"name": "Faculty FDP Corporate", "icon": "fa-building", "description": "Corporate FDP and training.", "categories": {"fdp": "Corporate FDP", "training": "Corporate Training"}},
    "faculty_fdp_inhouse": {"name": "Faculty FDP Inhouse", "icon": "fa-chalkboard-user", "description": "In-house FDP and faculty training.", "categories": {"fdp": "Inhouse FDP", "training": "Faculty Training"}},
    "library": {"name": "Library", "icon": "fa-book", "description": "Books, journals and electronic resources.", "categories": {"books": "Books", "journals": "Journals", "e_resources": "E-Resources"}},
    "moocs": {"name": "MOOCs", "icon": "fa-laptop", "description": "MOOC courses and certifications.", "categories": {"courses": "MOOC Courses", "certifications": "Certifications"}},
    "mous_international": {"name": "MOUs International", "icon": "fa-handshake", "description": "International MOUs and collaboration.", "categories": {"mou": "International MOUs", "collaboration": "International Collaboration"}},
    "p_and_d": {"name": "Planning and Development", "icon": "fa-chart-line", "description": "Planning and institutional development.", "categories": {"planning": "Planning", "development": "Development"}},
    "placements": {"name": "Placements", "icon": "fa-briefcase", "description": "Placements, internships and higher education.", "categories": {"placements": "Placements", "internships": "Internships", "higher_education": "Higher Education"}},
    "progression": {"name": "Progression", "icon": "fa-arrow-trend-up", "description": "Student and career progression.", "categories": {"students": "Student Progression", "career": "Career Progression"}},
    "registrar_office": {"name": "Registrar Office", "icon": "fa-building-columns", "description": "Official records and administration.", "categories": {"records": "Records", "administration": "Administration"}},
    "research": {"name": "Research", "icon": "fa-flask", "description": "Publications, projects and patents.", "categories": {"publications": "Publications", "projects": "Research Projects", "patents": "Patents"}},
    "sac": {"name": "SAC", "icon": "fa-people-group", "description": "Student activities, clubs and events.", "categories": {"activities": "Student Activities", "clubs": "Clubs", "events": "Events"}},
    "student_abroad_program": {"name": "Student Abroad Program", "icon": "fa-earth-americas", "description": "Student exchange and study abroad.", "categories": {"exchange": "Student Exchange", "abroad": "Study Abroad"}},
    "student_entrepreneurship": {"name": "Student Entrepreneurship", "icon": "fa-lightbulb", "description": "Startups and entrepreneurship.", "categories": {"startups": "Startups", "entrepreneurship": "Entrepreneurship"}},
    "visiting_faculty": {"name": "Visiting Faculty", "icon": "fa-user-group", "description": "Visiting and international faculty.", "categories": {"faculty": "Visiting Faculty", "international": "International Faculty"}},
    "workload_of_students": {"name": "Workload of Students", "icon": "fa-clock", "description": "Student workload and credits.", "categories": {"workload": "Student Workload", "credits": "Credits"}},
}

MODULE_ALIASES = {"faculty_exchange": "faculty_exchange_abroad", "placementa": "placements"}

MODULE_KEYWORDS = {
    "academics": ["academic", "syllabus", "curriculum", "course", "courses", "co attainment", "po attainment"],
    "counselling": ["counselling", "counseling", "mental health", "career counselling"],
    "exams_evaluation": ["exam", "examination", "evaluation", "result", "marks", "assessment"],
    "faculty_affairs": ["faculty affairs", "faculty information", "faculty development"],
    "faculty_exchange_abroad": ["faculty exchange", "faculty abroad", "international faculty"],
    "faculty_fdp_corporate": ["corporate fdp", "corporate training"],
    "faculty_fdp_inhouse": ["inhouse fdp", "in-house fdp", "faculty development programme", "faculty development program"],
    "library": ["library", "book", "books", "journal", "journals", "e-resource", "e resources"],
    "moocs": ["mooc", "moocs", "online course", "online certification"],
    "mous_international": ["mou", "memorandum", "international collaboration"],
    "p_and_d": ["planning and development", "planning", "institutional development"],
    "placements": ["placement", "placements", "internship", "internships", "higher education", "recruiter", "package", "ctc", "company"],
    "progression": ["progression", "career progression", "student progression"],
    "registrar_office": ["registrar", "registration", "official record"],
    "research": ["research", "publication", "publications", "paper", "patent", "research project"],
    "sac": ["sac", "student activity", "club", "clubs", "student event"],
    "student_abroad_program": ["student abroad", "study abroad", "student exchange"],
    "student_entrepreneurship": ["entrepreneur", "entrepreneurship", "startup", "startups"],
    "visiting_faculty": ["visiting faculty", "guest faculty"],
    "workload_of_students": ["student workload", "workload", "credits"],
}


def normalize_module(module):
    module = (module or "").strip().lower()
    return MODULE_ALIASES.get(module, module)


def row_text(row):
    values = []
    for value in row.values:
        if pd.isna(value):
            continue
        values.append(str(value))
    return " ".join(values).lower()


def detect_module(row, sheet_name="", extra_text=""):
    text = f"{sheet_name} {extra_text} {row_text(row)}".lower()
    best_module = "academics"
    best_score = 0
    for module, keywords in MODULE_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best_score = score
            best_module = module
    return best_module


def detect_category(module, row, sheet_name=""):
    module = normalize_module(module)
    text = f"{sheet_name} {row_text(row)}".lower()
    categories = MODULES[module]["categories"]
    for key, label in categories.items():
        key_text = key.replace("_", " ")
        label_words = re.findall(r"[a-z0-9]+", label.lower())
        if key_text in text or label.lower() in text or all(word in text for word in label_words if len(word) > 2):
            return key
    return next(iter(categories))


def detect_source_type(url):
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    path = parsed.path.lower()
    if "docs.google.com/spreadsheets" in url.lower():
        return "google_sheets"
    if "drive.google.com" in host:
        return "google_drive"
    if path.endswith((".xlsx", ".xls")):
        return "excel"
    if path.endswith(".csv"):
        return "csv"
    return "other"


def clean_columns(columns):
    result = []
    used = {}
    for index, column in enumerate(columns, 1):
        name = str(column).strip() or f"Column_{index}"
        count = used.get(name, 0) + 1
        used[name] = count
        if count > 1:
            name = f"{name}_{count}"
        result.append(name)
    return result


def _json_value(value):
    if pd.isna(value):
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _row_dict(row):
    return {str(k): _json_value(v) for k, v in row.items()}


def create_dataset(user_id, title, source_url, upload_mode="mixed", target_module=None, target_category=None):
    upload_mode = upload_mode if upload_mode in ("mixed", "specific") else "mixed"
    target_module = normalize_module(target_module)
    if target_module not in MODULES:
        target_module = None
        target_category = None

    source_type = detect_source_type(source_url)
    connection = get_connection()
    try:
        cur = connection.execute(
            """INSERT INTO uploads
               (uploaded_by,title,source_url,upload_method,source_type,upload_mode,target_module,target_category,status)
               VALUES (?,?,?,'link',?,?,?,?, 'processing')""",
            (user_id, title or "Imported Dataset", source_url, source_type, upload_mode, target_module, target_category),
        )
        upload_id = cur.lastrowid
        connection.execute(
            "INSERT INTO dataset_refresh_logs (upload_id,status,message) VALUES (?, 'started', ?)",
            (upload_id, "Data import started."),
        )
        connection.commit()
    finally:
        connection.close()

    try:
        file_path, filename = download_spreadsheet(source_url)
        file_path = Path(file_path)
        try:
            if file_path.suffix.lower() == ".csv":
                sheets = {"Sheet1": pd.read_csv(file_path)}
            else:
                sheets = pd.read_excel(file_path, sheet_name=None)
            save_sheets(upload_id, sheets, upload_mode, target_module, target_category)
            return upload_id, True, None
        finally:
            file_path.unlink(missing_ok=True)
    except Exception as error:
        mark_dataset_failed(upload_id, str(error))
        return upload_id, False, str(error)


def save_sheets(upload_id, sheets, upload_mode="mixed", target_module=None, target_category=None):
    connection = get_connection()
    try:
        connection.execute("DELETE FROM records WHERE upload_id = ?", (upload_id,))
        connection.execute("DELETE FROM dataset_columns WHERE upload_id = ?", (upload_id,))
        total_rows = 0
        max_columns = 0
        column_index_by_name = {}

        for sheet_name, dataframe in sheets.items():
            if dataframe is None:
                continue
            dataframe = dataframe.dropna(how="all")
            if dataframe.empty:
                continue
            dataframe.columns = clean_columns(dataframe.columns)
            max_columns = max(max_columns, len(dataframe.columns))

            for index, column in enumerate(dataframe.columns):
                if str(column) not in column_index_by_name:
                    column_index_by_name[str(column)] = len(column_index_by_name)
                    if pd.api.types.is_numeric_dtype(dataframe[column]):
                        dtype = "number"
                    elif pd.api.types.is_datetime64_any_dtype(dataframe[column]):
                        dtype = "date"
                    else:
                        dtype = "text"
                    connection.execute(
                        "INSERT INTO dataset_columns (upload_id,column_index,column_name,data_type) VALUES (?,?,?,?)",
                        (upload_id, column_index_by_name[str(column)], str(column), dtype),
                    )

            header_text = " ".join(str(column) for column in dataframe.columns)
            sample_text = " ".join(str(value) for value in dataframe.head(5).fillna("").astype(str).values.flatten())
            sheet_module = detect_module(pd.Series([], dtype=object), sheet_name, f"{header_text} {sample_text}")
            for row_number, (_, row) in enumerate(dataframe.iterrows(), start=2):
                if upload_mode == "specific" and target_module:
                    module = target_module
                    category = target_category or detect_category(module, row, sheet_name)
                else:
                    row_module = detect_module(row, sheet_name, header_text)
                    module = row_module if row_module != "academics" or sheet_module == "academics" else sheet_module
                    category = detect_category(module, row, sheet_name)
                connection.execute(
                    """INSERT INTO records
                       (upload_id,module_key,category_key,sheet_name,row_number,row_data)
                       VALUES (?,?,?,?,?,?)""",
                    (upload_id, module, category, str(sheet_name), row_number, json.dumps(_row_dict(row), ensure_ascii=False)),
                )
                total_rows += 1

        connection.execute(
            """UPDATE uploads SET status='completed', row_count=?, column_count=?, error_message=NULL,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (total_rows, max_columns, upload_id),
        )
        connection.execute(
            """UPDATE dataset_refresh_logs SET status='completed', rows_imported=?, columns_imported=?, message=?
               WHERE upload_id=? AND status='started'""",
            (total_rows, max_columns, "Import completed successfully.", upload_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def mark_dataset_failed(upload_id, error_message):
    connection = get_connection()
    try:
        connection.execute("UPDATE uploads SET status='failed', error_message=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (error_message, upload_id))
        connection.execute("UPDATE dataset_refresh_logs SET status='failed', message=? WHERE upload_id=? AND status='started'", (error_message, upload_id))
        connection.commit()
    finally:
        connection.close()


def get_uploads():
    connection = get_connection()
    try:
        rows = connection.execute(
            """SELECT u.*, users.name AS uploader_name, users.email AS uploader_email
               FROM uploads u LEFT JOIN users ON users.id=u.uploaded_by
               ORDER BY u.created_at DESC"""
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["filename"] = item.get("title")
            item["uploader"] = item.get("uploader_name")
            result.append(item)
        return result
    finally:
        connection.close()


def get_all_uploads():
    return get_uploads()


def get_all_datasets():
    return get_uploads()


def get_user_uploads(user_id):
    connection = get_connection()
    try:
        rows = connection.execute("SELECT * FROM uploads WHERE uploaded_by=? ORDER BY created_at DESC", (user_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_user_datasets(user_id):
    return get_user_uploads(user_id)


def get_upload(upload_id):
    connection = get_connection()
    try:
        row = connection.execute(
            """SELECT u.*, users.name AS uploader_name, users.email AS uploader_email
               FROM uploads u LEFT JOIN users ON users.id=u.uploaded_by WHERE u.id=? LIMIT 1""",
            (upload_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def _decorate(row):
    item = dict(row)
    data = json.loads(item.get("row_data") or "{}")
    item["row_data"] = data
    item["data"] = data
    item["module"] = item.get("module_key")
    item["category"] = item.get("category_key")
    item["filename"] = item.get("title")
    item["uploader"] = item.get("uploader_name")
    return item


def get_dataset_rows(upload_id, module=None, category=None):
    query = "SELECT r.*, u.title, u.source_url, users.name AS uploader_name, users.email AS uploader_email FROM records r JOIN uploads u ON u.id=r.upload_id LEFT JOIN users ON users.id=u.uploaded_by WHERE r.upload_id=?"
    params = [upload_id]
    if module:
        query += " AND r.module_key=?"
        params.append(normalize_module(module))
    if category:
        query += " AND r.category_key=?"
        params.append(category)
    query += " ORDER BY r.sheet_name, r.row_number"
    connection = get_connection()
    try:
        return [_decorate(row) for row in connection.execute(query, params).fetchall()]
    finally:
        connection.close()


def get_all_rows(module=None, category=None, upload_id=None):
    query = "SELECT r.*, u.title, u.source_url, u.uploaded_by, users.name AS uploader_name, users.email AS uploader_email FROM records r JOIN uploads u ON u.id=r.upload_id LEFT JOIN users ON users.id=u.uploaded_by WHERE 1=1"
    params = []
    if module:
        query += " AND r.module_key=?"
        params.append(normalize_module(module))
    if category:
        query += " AND r.category_key=?"
        params.append(category)
    if upload_id:
        query += " AND r.upload_id=?"
        params.append(upload_id)
    query += " ORDER BY u.created_at DESC, r.sheet_name, r.row_number"
    connection = get_connection()
    try:
        return [_decorate(row) for row in connection.execute(query, params).fetchall()]
    finally:
        connection.close()


def get_module_data(module_key):
    module_key = normalize_module(module_key)
    grouped = {key: [] for key in MODULES[module_key]["categories"]}
    for row in get_all_rows(module=module_key):
        grouped.setdefault(row["category"], []).append(row)
    return grouped


def prepare_module_tables(grouped_data):
    tables = []
    for category_key, rows in grouped_data.items():
        columns = []
        for row in rows:
            for column in row.get("data", {}):
                if column not in columns:
                    columns.append(column)
        tables.append({"key": category_key, "rows": rows, "columns": columns})
    return tables


def numeric_averages(rows):
    totals = {}
    counts = {}
    for row in rows:
        for field, value in row.get("data", {}).items():
            name = str(field).lower()
            if name == "id" or name.endswith("_id") or name.endswith("id"):
                continue
            try:
                number = float(str(value).replace(",", "").strip())
            except (TypeError, ValueError):
                continue
            totals[field] = totals.get(field, 0) + number
            counts[field] = counts.get(field, 0) + 1
    return {field: round(totals[field] / counts[field], 2) for field in totals if counts[field]}


def build_module_report(module_key, grouped_data=None):
    module_key = normalize_module(module_key)
    grouped_data = grouped_data if grouped_data is not None else get_module_data(module_key)
    rows = [row for values in grouped_data.values() for row in values]
    return {
        "module_key": module_key,
        "module_name": MODULES[module_key]["name"],
        "total_records": len(rows),
        "category_counts": {key: len(values) for key, values in grouped_data.items()},
        "numeric_averages": numeric_averages(rows),
    }


def get_report():
    uploads = get_uploads()
    modules = []
    total_records = 0
    populated_categories = 0
    for key, info in MODULES.items():
        grouped = get_module_data(key)
        report = build_module_report(key, grouped)
        categories = []
        for cat_key, values in grouped.items():
            cat_name = info["categories"].get(cat_key, str(cat_key).replace("_", " ").replace("-", " ").title())
            count = len(values)
            if count:
                populated_categories += 1
            categories.append({"key": cat_key, "name": cat_name, "count": count})
        total_records += report["total_records"]
        modules.append({"key": key, "name": info["name"], "description": info["description"], "icon": info["icon"], "total_records": report["total_records"], "categories": categories, "numeric_averages": [{"field": k, "value": v} for k, v in report["numeric_averages"].items()][:8]})
    return {
        "generated_at": pd.Timestamp.now().strftime("%d %b %Y, %I:%M %p"),
        "total_records": total_records,
        "total_uploads": len(uploads),
        "populated_modules": sum(1 for m in modules if m["total_records"] > 0),
        "total_modules": len(MODULES),
        "populated_categories": populated_categories,
        "total_categories": sum(len(m["categories"]) for m in modules),
        "modules": modules,
        "recent_uploads": uploads[:8],
    }


def delete_upload(upload_id):
    connection = get_connection()
    try:
        cur = connection.execute("DELETE FROM uploads WHERE id=?", (upload_id,))
        connection.commit()
        return cur.rowcount > 0
    finally:
        connection.close()
