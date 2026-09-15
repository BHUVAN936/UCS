from pathlib import Path
import sqlite3

from config import Config

SCHEMA_VERSION = 2


def get_connection():
    database_path = Path(Config.DATABASE_PATH)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(database_path), timeout=30, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def _columns(connection, table):
    return [row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()]


def _table_exists(connection, table):
    return connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def _rename_if_exists(connection, old, new):
    if _table_exists(connection, old) and not _table_exists(connection, new):
        connection.execute(f'ALTER TABLE "{old}" RENAME TO "{new}"')


def init_database():
    connection = get_connection()
    try:
        # The database shipped with the old project used uploads/records with a
        # different schema. Move those tables aside once, then create the schema
        # from database/schema.sql. This prevents "no column" and FK errors.
        upload_columns = _columns(connection, "uploads") if _table_exists(connection, "uploads") else []
        if upload_columns and "title" not in upload_columns:
            _rename_if_exists(connection, "uploads", "legacy_uploads")
            _rename_if_exists(connection, "records", "legacy_records")
            _rename_if_exists(connection, "dataset_columns", "legacy_dataset_columns")
            _rename_if_exists(connection, "dataset_refresh_logs", "legacy_dataset_refresh_logs")

        # The old users table did not have updated_at.
        if _table_exists(connection, "users") and "updated_at" not in _columns(connection, "users"):
            connection.execute("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP")
            connection.execute("UPDATE users SET updated_at=CURRENT_TIMESTAMP WHERE updated_at IS NULL")

        schema_path = Path(__file__).resolve().parent / "schema.sql"
        connection.executescript(schema_path.read_text(encoding="utf-8"))

        # Preserve old link submissions if they exist. Old file uploads without
        # a link are intentionally not migrated as usable link submissions.
        if _table_exists(connection, "legacy_uploads"):
            old_cols = _columns(connection, "legacy_uploads")
            if "source_url" in old_cols:
                connection.execute("""
                    INSERT OR IGNORE INTO uploads
                    (id, uploaded_by, title, source_url, upload_method, source_type,
                     upload_mode, target_module, target_category, status, error_message,
                     row_count, column_count, created_at, updated_at)
                    SELECT id,
                           uploaded_by,
                           COALESCE(filename, 'Legacy Dataset'),
                           COALESCE(source_url, ''),
                           'link',
                           CASE WHEN source_url LIKE '%docs.google.com/spreadsheets%' THEN 'google_sheets'
                                WHEN source_url LIKE '%drive.google.com%' THEN 'google_drive'
                                ELSE 'other' END,
                           CASE WHEN upload_mode IN ('mixed','specific') THEN upload_mode ELSE 'mixed' END,
                           target_module,
                           target_category,
                           CASE WHEN status IN ('pending','processing','completed','failed') THEN status ELSE 'completed' END,
                           NULL,
                           COALESCE(row_count,0),
                           0,
                           COALESCE(created_at,CURRENT_TIMESTAMP),
                           COALESCE(created_at,CURRENT_TIMESTAMP)
                    FROM legacy_uploads
                    WHERE COALESCE(source_url,'') <> ''
                """)

        # Preserve the old record table when its rows belong to an old upload.
        if _table_exists(connection, "legacy_records"):
            old_cols = _columns(connection, "legacy_records")
            if {"upload_id", "module", "category", "data_json"}.issubset(old_cols):
                connection.execute("""
                    INSERT INTO records
                    (upload_id,module_key,category_key,sheet_name,row_number,row_data)
                    SELECT r.upload_id,
                           COALESCE(r.module,'academics'),
                           r.category,
                           'Legacy Data',
                           COALESCE(r.id,1),
                           COALESCE(r.data_json,'{}')
                    FROM legacy_records r
                    JOIN uploads u ON u.id=r.upload_id
                """)

        # Legacy copies are no longer needed after the one-time migration.
        for legacy_table in (
            "legacy_records",
            "legacy_dataset_columns",
            "legacy_dataset_refresh_logs",
            "legacy_uploads",
        ):
            if _table_exists(connection, legacy_table):
                connection.execute(f'DROP TABLE "{legacy_table}"')

        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.commit()
    finally:
        connection.close()


# Compatibility helpers used by the rest of the project.

def create_user(name, email, password_hash, role="user"):
    connection = get_connection()
    try:
        cursor = connection.execute(
            "INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)",
            (name, email, password_hash, role),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def get_user_by_email(email):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id,name,email,password_hash,role,created_at FROM users WHERE email=? COLLATE NOCASE LIMIT 1",
            (email,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def get_user_by_id(user_id):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT id,name,email,role,created_at FROM users WHERE id=? LIMIT 1",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def create_upload(uploaded_by, title, source_url, source_type="other", upload_mode="mixed", target_module=None, target_category=None):
    connection = get_connection()
    try:
        cursor = connection.execute(
            """INSERT INTO uploads(uploaded_by,title,source_url,upload_method,source_type,upload_mode,target_module,target_category)
               VALUES(?,?,?,'link',?,?,?,?)""",
            (uploaded_by, title, source_url, source_type, upload_mode, target_module, target_category),
        )
        connection.commit()
        return cursor.lastrowid
    finally:
        connection.close()


def get_upload(upload_id):
    connection = get_connection()
    try:
        row = connection.execute(
            """SELECT uploads.*, users.name AS uploader_name, users.email AS uploader_email
               FROM uploads LEFT JOIN users ON users.id=uploads.uploaded_by WHERE uploads.id=? LIMIT 1""",
            (upload_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def get_all_uploads():
    connection = get_connection()
    try:
        rows = connection.execute(
            """SELECT uploads.*, users.name AS uploader_name, users.email AS uploader_email
               FROM uploads LEFT JOIN users ON users.id=uploads.uploaded_by ORDER BY uploads.created_at DESC"""
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_user_uploads(user_id):
    connection = get_connection()
    try:
        rows = connection.execute("SELECT * FROM uploads WHERE uploaded_by=? ORDER BY created_at DESC", (user_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def update_upload_status(upload_id, status, error_message=None, row_count=0, column_count=0):
    connection = get_connection()
    try:
        connection.execute(
            "UPDATE uploads SET status=?,error_message=?,row_count=?,column_count=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, error_message, row_count, column_count, upload_id),
        )
        connection.commit()
    finally:
        connection.close()


def insert_column(upload_id, column_index, column_name, data_type="text"):
    connection = get_connection()
    try:
        connection.execute(
            "INSERT OR REPLACE INTO dataset_columns(upload_id,column_index,column_name,data_type) VALUES(?,?,?,?)",
            (upload_id, column_index, column_name, data_type),
        )
        connection.commit()
    finally:
        connection.close()


def insert_record(upload_id, module_key, category_key, sheet_name, row_number, row_data):
    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO records(upload_id,module_key,category_key,sheet_name,row_number,row_data) VALUES(?,?,?,?,?,?)",
            (upload_id, module_key, category_key, sheet_name, row_number, row_data),
        )
        connection.commit()
    finally:
        connection.close()


def insert_records_batch(records):
    if not records:
        return
    connection = get_connection()
    try:
        connection.executemany(
            "INSERT INTO records(upload_id,module_key,category_key,sheet_name,row_number,row_data) VALUES(?,?,?,?,?,?)",
            records,
        )
        connection.commit()
    finally:
        connection.close()


def delete_upload_records(upload_id):
    connection = get_connection()
    try:
        connection.execute("DELETE FROM records WHERE upload_id=?", (upload_id,))
        connection.execute("DELETE FROM dataset_columns WHERE upload_id=?", (upload_id,))
        connection.commit()
    finally:
        connection.close()


def get_records_for_module(module_key, category_key=None):
    connection = get_connection()
    try:
        query = """SELECT records.*, uploads.title, uploads.source_url FROM records
                   JOIN uploads ON uploads.id=records.upload_id WHERE records.module_key=?"""
        params = [module_key]
        if category_key:
            query += " AND records.category_key=?"
            params.append(category_key)
        query += " ORDER BY records.created_at DESC, records.row_number"
        return [dict(row) for row in connection.execute(query, params).fetchall()]
    finally:
        connection.close()


def get_all_records():
    connection = get_connection()
    try:
        rows = connection.execute(
            """SELECT records.*, uploads.title, uploads.source_url,
                      users.name AS uploader_name, users.email AS uploader_email
               FROM records JOIN uploads ON uploads.id=records.upload_id
               LEFT JOIN users ON users.id=uploads.uploaded_by
               ORDER BY records.module_key, records.category_key, records.created_at DESC, records.row_number"""
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_module_statistics():
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT module_key,category_key,COUNT(*) AS total FROM records GROUP BY module_key,category_key ORDER BY module_key,category_key"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def delete_upload(upload_id):
    connection = get_connection()
    try:
        cursor = connection.execute("DELETE FROM uploads WHERE id=?", (upload_id,))
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()
