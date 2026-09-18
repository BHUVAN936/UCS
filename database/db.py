import json
import sqlite3
from pathlib import Path

from config import Config


# ============================================================
# DATABASE VERSION
# ============================================================

SCHEMA_VERSION = 4


# ============================================================
# CONNECTION
# ============================================================

def get_connection():
    """
    Create and configure a SQLite database connection.
    """

    database_path = Path(Config.DATABASE_PATH)

    database_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(
        str(database_path),
        timeout=30,
        check_same_thread=False
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    connection.execute(
        "PRAGMA synchronous = NORMAL"
    )

    connection.execute(
        "PRAGMA busy_timeout = 30000"
    )

    return connection


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _table_exists(connection, table_name):
    return (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
            LIMIT 1
            """,
            (table_name,)
        ).fetchone()
        is not None
    )


def _columns(connection, table_name):

    if not _table_exists(
        connection,
        table_name
    ):
        return []

    return [
        row[1]
        for row in connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()
    ]


def _add_column_if_missing(
    connection,
    table_name,
    column_name,
    definition
):
    columns = _columns(
        connection,
        table_name
    )

    if column_name not in columns:
        connection.execute(
            f'ALTER TABLE "{table_name}" '
            f'ADD COLUMN "{column_name}" {definition}'
        )


def _rename_if_exists(
    connection,
    old_name,
    new_name
):
    if (
        _table_exists(connection, old_name)
        and not _table_exists(connection, new_name)
    ):
        connection.execute(
            f'ALTER TABLE "{old_name}" '
            f'RENAME TO "{new_name}"'
        )


def _safe_drop(
    connection,
    table_name
):
    if _table_exists(
        connection,
        table_name
    ):
        connection.execute(
            f'DROP TABLE "{table_name}"'
        )


# ============================================================
# SCHEMA CREATION
# ============================================================

def _create_tables(connection):
    """
    Create the complete current UCE_Connect database schema.
    """

    # --------------------------------------------------------
    # USERS
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT NOT NULL UNIQUE COLLATE NOCASE,

            password_hash TEXT NOT NULL,

            role TEXT NOT NULL DEFAULT 'user'
                CHECK(role IN ('user', 'admin')),

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            updated_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            last_login_at TIMESTAMP,

            last_seen_at TIMESTAMP
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_users_email
        ON users(email)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_users_role
        ON users(role)
        """
    )


    # --------------------------------------------------------
    # ADMINS
    # --------------------------------------------------------
    #
    # The users.role column remains the main source of truth.
    # This table is an optional admin registry and does not
    # replace users.
    #

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL UNIQUE,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )


    # --------------------------------------------------------
    # UPLOADS / LINK SUBMISSIONS
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            uploaded_by INTEGER,

            title TEXT NOT NULL,

            source_url TEXT NOT NULL,

            upload_method TEXT
                NOT NULL DEFAULT 'link',

            source_type TEXT
                NOT NULL DEFAULT 'other',

            upload_mode TEXT
                NOT NULL DEFAULT 'mixed',

            target_module TEXT,

            target_category TEXT,

            status TEXT
                NOT NULL DEFAULT 'pending',

            error_message TEXT,

            row_count INTEGER
                NOT NULL DEFAULT 0,

            column_count INTEGER
                NOT NULL DEFAULT 0,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            updated_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(uploaded_by)
                REFERENCES users(id)
                ON DELETE SET NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_uploads_uploaded_by
        ON uploads(uploaded_by)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_uploads_created_at
        ON uploads(created_at)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_uploads_module
        ON uploads(target_module)
        """
    )


    # --------------------------------------------------------
    # DATA RECORDS
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            upload_id INTEGER NOT NULL,

            module_key TEXT NOT NULL
                DEFAULT 'unclassified',

            category_key TEXT NOT NULL
                DEFAULT 'unclassified',

            sheet_name TEXT,

            row_number INTEGER
                NOT NULL DEFAULT 1,

            row_data TEXT
                NOT NULL DEFAULT '{}',

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(upload_id)
                REFERENCES uploads(id)
                ON DELETE CASCADE
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_records_upload
        ON records(upload_id)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_records_module
        ON records(module_key)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_records_category
        ON records(category_key)
        """
    )


    # --------------------------------------------------------
    # DATASET COLUMNS
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS dataset_columns (
            upload_id INTEGER NOT NULL,

            column_index INTEGER NOT NULL,

            column_name TEXT NOT NULL,

            data_type TEXT
                NOT NULL DEFAULT 'text',

            PRIMARY KEY(
                upload_id,
                column_index
            ),

            FOREIGN KEY(upload_id)
                REFERENCES uploads(id)
                ON DELETE CASCADE
        )
        """
    )


    # --------------------------------------------------------
    # DATASET REFRESH LOGS
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS dataset_refresh_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            upload_id INTEGER NOT NULL,

            status TEXT
                NOT NULL,

            row_count INTEGER
                DEFAULT 0,

            column_count INTEGER
                DEFAULT 0,

            error_message TEXT,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(upload_id)
                REFERENCES uploads(id)
                ON DELETE CASCADE
        )
        """
    )


    # --------------------------------------------------------
    # APPLICATION SETTINGS
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_key TEXT NOT NULL UNIQUE,
            setting_value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_app_settings_key
        ON app_settings(setting_key)
        """
    )


    # --------------------------------------------------------
    # PASSWORD RESET TOKENS
    # --------------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            token_hash TEXT NOT NULL UNIQUE,

            expires_at TEXT NOT NULL,

            used_at TEXT,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_password_reset_token_hash
        ON password_reset_tokens(token_hash)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_password_reset_user
        ON password_reset_tokens(
            user_id,
            created_at
        )
        """
    )


def _migrate_refresh_logs(connection):
    """Migrate the previous refresh-log column names to the current schema."""
    if not _table_exists(connection, "dataset_refresh_logs"):
        return

    columns = set(_columns(connection, "dataset_refresh_logs"))
    if "row_count" in columns:
        return

    if not {"rows_imported", "columns_imported", "message"}.issubset(columns):
        return

    _rename_if_exists(
        connection,
        "dataset_refresh_logs",
        "legacy_dataset_refresh_logs_v1",
    )

    connection.execute(
        """
        CREATE TABLE dataset_refresh_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upload_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            row_count INTEGER DEFAULT 0,
            column_count INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(upload_id) REFERENCES uploads(id) ON DELETE CASCADE
        )
        """
    )

    connection.execute(
        """
        INSERT INTO dataset_refresh_logs
            (id, upload_id, status, row_count, column_count, error_message, created_at)
        SELECT
            id, upload_id, status, rows_imported, columns_imported, message, created_at
        FROM legacy_dataset_refresh_logs_v1
        """
    )

    _safe_drop(connection, "legacy_dataset_refresh_logs_v1")


# ============================================================
# DATABASE MIGRATION
# ============================================================

def _migrate_users(connection):

    if not _table_exists(
        connection,
        "users"
    ):
        return

    # Older versions may not contain these fields.
    _add_column_if_missing(
        connection,
        "users",
        "updated_at",
        "TIMESTAMP"
    )

    _add_column_if_missing(
        connection,
        "users",
        "last_login_at",
        "TIMESTAMP"
    )

    _add_column_if_missing(
        connection,
        "users",
        "last_seen_at",
        "TIMESTAMP"
    )

    connection.execute(
        """
        UPDATE users
        SET updated_at = CURRENT_TIMESTAMP
        WHERE updated_at IS NULL
        """
    )


def _migrate_uploads(connection):

    if not _table_exists(
        connection,
        "uploads"
    ):
        return

    columns = _columns(
        connection,
        "uploads"
    )

    # If the old table is clearly incompatible,
    # move it aside so the new schema can be created.
    if "title" not in columns:

        _rename_if_exists(
            connection,
            "uploads",
            "legacy_uploads"
        )

        _rename_if_exists(
            connection,
            "records",
            "legacy_records"
        )

        _rename_if_exists(
            connection,
            "dataset_columns",
            "legacy_dataset_columns"
        )

        _rename_if_exists(
            connection,
            "dataset_refresh_logs",
            "legacy_dataset_refresh_logs"
        )


def _migrate_legacy_data(connection):

    # --------------------------------------------------------
    # LEGACY UPLOADS
    # --------------------------------------------------------

    if _table_exists(
        connection,
        "legacy_uploads"
    ):

        old_columns = _columns(
            connection,
            "legacy_uploads"
        )

        required = {
            "id",
            "uploaded_by",
            "source_url"
        }

        if required.issubset(
            set(old_columns)
        ):

            filename_expression = (
                "filename"
                if "filename" in old_columns
                else "NULL"
            )

            upload_mode_expression = (
                "upload_mode"
                if "upload_mode" in old_columns
                else "'mixed'"
            )

            target_module_expression = (
                "target_module"
                if "target_module" in old_columns
                else "NULL"
            )

            target_category_expression = (
                "target_category"
                if "target_category" in old_columns
                else "NULL"
            )

            status_expression = (
                "status"
                if "status" in old_columns
                else "'completed'"
            )

            row_count_expression = (
                "row_count"
                if "row_count" in old_columns
                else "0"
            )

            created_expression = (
                "created_at"
                if "created_at" in old_columns
                else "CURRENT_TIMESTAMP"
            )

            connection.execute(
                f"""
                INSERT OR IGNORE INTO uploads
                (
                    id,
                    uploaded_by,
                    title,
                    source_url,
                    upload_method,
                    source_type,
                    upload_mode,
                    target_module,
                    target_category,
                    status,
                    error_message,
                    row_count,
                    column_count,
                    created_at,
                    updated_at
                )
                SELECT
                    id,

                    uploaded_by,

                    COALESCE(
                        NULLIF(
                            TRIM(
                                {filename_expression}
                            ),
                            ''
                        ),
                        'Legacy Dataset'
                    ),

                    source_url,

                    'link',

                    CASE
                        WHEN LOWER(source_url)
                            LIKE '%docs.google.com/spreadsheets%'
                        THEN 'google_sheets'

                        WHEN LOWER(source_url)
                            LIKE '%drive.google.com%'
                        THEN 'google_drive'

                        WHEN LOWER(source_url)
                            LIKE '%.csv%'
                        THEN 'csv'

                        WHEN LOWER(source_url)
                            LIKE '%.xls%'
                        THEN 'excel'

                        ELSE 'other'
                    END,

                    CASE
                        WHEN {upload_mode_expression}
                            IN ('mixed', 'specific')
                        THEN {upload_mode_expression}
                        ELSE 'mixed'
                    END,

                    {target_module_expression},

                    {target_category_expression},

                    CASE
                        WHEN {status_expression}
                            IN (
                                'pending',
                                'processing',
                                'completed',
                                'failed'
                            )
                        THEN {status_expression}
                        ELSE 'completed'
                    END,

                    NULL,

                    COALESCE(
                        {row_count_expression},
                        0
                    ),

                    0,

                    COALESCE(
                        {created_expression},
                        CURRENT_TIMESTAMP
                    ),

                    COALESCE(
                        {created_expression},
                        CURRENT_TIMESTAMP
                    )

                FROM legacy_uploads

                WHERE
                    source_url IS NOT NULL
                    AND TRIM(source_url) <> ''
                """
            )


    # --------------------------------------------------------
    # LEGACY RECORDS
    # --------------------------------------------------------

    if _table_exists(
        connection,
        "legacy_records"
    ):

        old_columns = _columns(
            connection,
            "legacy_records"
        )

        if {
            "upload_id",
            "data_json"
        }.issubset(
            set(old_columns)
        ):

            module_expression = (
                "module"
                if "module" in old_columns
                else "'unclassified'"
            )

            category_expression = (
                "category"
                if "category" in old_columns
                else "'unclassified'"
            )

            id_expression = (
                "id"
                if "id" in old_columns
                else "1"
            )

            connection.execute(
                f"""
                INSERT INTO records
                (
                    upload_id,
                    module_key,
                    category_key,
                    sheet_name,
                    row_number,
                    row_data
                )

                SELECT

                    r.upload_id,

                    CASE
                        WHEN TRIM(
                            COALESCE(
                                {module_expression},
                                ''
                            )
                        ) = ''
                        THEN 'unclassified'

                        WHEN LOWER(
                            TRIM(
                                {module_expression}
                            )
                        ) IN (
                            'alumni',
                            'finance'
                        )
                        THEN 'unclassified'

                        ELSE LOWER(
                            REPLACE(
                                TRIM(
                                    {module_expression}
                                ),
                                ' ',
                                '_'
                            )
                        )
                    END,

                    CASE
                        WHEN TRIM(
                            COALESCE(
                                {category_expression},
                                ''
                            )
                        ) = ''
                        THEN 'unclassified'

                        ELSE LOWER(
                            REPLACE(
                                TRIM(
                                    {category_expression}
                                ),
                                ' ',
                                '_'
                            )
                        )
                    END,

                    'Legacy Data',

                    COALESCE(
                        {id_expression},
                        1
                    ),

                    COALESCE(
                        r.data_json,
                        '{{}}'
                    )

                FROM legacy_records r

                INNER JOIN uploads u
                    ON u.id = r.upload_id
                """
            )


    # --------------------------------------------------------
    # LEGACY TABLE CLEANUP
    # --------------------------------------------------------

    for table_name in (
        "legacy_records",
        "legacy_dataset_columns",
        "legacy_dataset_refresh_logs",
        "legacy_uploads"
    ):

        _safe_drop(
            connection,
            table_name
        )


def _cleanup_obsolete_tables(connection):
    """Remove tables from the retired pre-records data model.

    These tables are not referenced by the current application. Keeping them
    creates two competing data models and makes database maintenance unsafe.
    """
    obsolete_tables = (
        "courses",
        "faculty",
        "dataset_rows",
        "dataset_submissions",
        "portal_data",
        "practice_school",
        "projects",
        "skills",
        "students",
        "training",
        "placements",
        "research",
        "upload_history",
    )

    for table_name in obsolete_tables:
        _safe_drop(connection, table_name)


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_database():

    connection = get_connection()

    try:

        # ----------------------------------------------------
        # MIGRATE EXISTING TABLES
        # ----------------------------------------------------

        _migrate_users(
            connection
        )

        _migrate_uploads(
            connection
        )

        _migrate_refresh_logs(
            connection
        )

        # ----------------------------------------------------
        # CREATE CURRENT TABLES
        # ----------------------------------------------------

        _create_tables(
            connection
        )

        # ----------------------------------------------------
        # MIGRATE OLD DATA
        # ----------------------------------------------------

        _migrate_legacy_data(
            connection
        )

        # ----------------------------------------------------
        # REMOVE RETIRED TABLES
        # ----------------------------------------------------

        _cleanup_obsolete_tables(
            connection
        )

        # ----------------------------------------------------
        # CREATE ADMINS FROM EXISTING ADMIN USERS
        # ----------------------------------------------------

        connection.execute(
            """
            INSERT OR IGNORE INTO admins(user_id)

            SELECT id
            FROM users
            WHERE LOWER(role) = 'admin'
            """
        )

        # ----------------------------------------------------
        # DATABASE VERSION
        # ----------------------------------------------------

        connection.execute(
            f"PRAGMA user_version = {SCHEMA_VERSION}"
        )

        connection.commit()

    except Exception:

        connection.rollback()

        raise

    finally:

        connection.close()


# ============================================================
# USER FUNCTIONS
# ============================================================

def create_user(
    name,
    email,
    password_hash,
    role="user"
):

    connection = get_connection()

    try:

        role = (
            "admin"
            if str(role).lower() == "admin"
            else "user"
        )

        cursor = connection.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password_hash,
                role,
                created_at,
                updated_at
            )
            VALUES
            (
                ?,
                ?,
                ?,
                ?,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """,
            (
                name,
                email.strip().lower(),
                password_hash,
                role
            )
        )

        user_id = cursor.lastrowid

        if role == "admin":

            connection.execute(
                """
                INSERT OR IGNORE INTO admins(user_id)
                VALUES(?)
                """,
                (user_id,)
            )

        connection.commit()

        return user_id

    finally:

        connection.close()


def get_user_by_email(email):

    connection = get_connection()

    try:

        row = connection.execute(
            """
            SELECT
                id,
                name,
                email,
                password_hash,
                role,
                created_at,
                updated_at,
                last_login_at,
                last_seen_at

            FROM users

            WHERE email = ?
            COLLATE NOCASE

            LIMIT 1
            """,
            (
                email.strip(),
            )
        ).fetchone()

        return (
            dict(row)
            if row
            else None
        )

    finally:

        connection.close()


def get_user_by_id(user_id):

    connection = get_connection()

    try:

        row = connection.execute(
            """
            SELECT
                id,
                name,
                email,
                role,
                created_at,
                updated_at,
                last_login_at,
                last_seen_at

            FROM users

            WHERE id = ?

            LIMIT 1
            """,
            (user_id,)
        ).fetchone()

        return (
            dict(row)
            if row
            else None
        )

    finally:

        connection.close()


def update_last_login(user_id):

    connection = get_connection()

    try:

        connection.execute(
            """
            UPDATE users

            SET
                last_login_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (user_id,)
        )

        connection.commit()

    finally:

        connection.close()


def update_last_seen(user_id):

    connection = get_connection()

    try:

        connection.execute(
            """
            UPDATE users

            SET last_seen_at = CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (user_id,)
        )

        connection.commit()

    finally:

        connection.close()


def update_user_password(
    user_id,
    password_hash
):

    connection = get_connection()

    try:

        cursor = connection.execute(
            """
            UPDATE users

            SET
                password_hash = ?,
                updated_at = CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                password_hash,
                user_id
            )
        )

        connection.commit()

        return cursor.rowcount > 0

    finally:

        connection.close()


def get_all_users():

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                id,
                name,
                email,
                role,
                created_at,
                updated_at,
                last_login_at,
                last_seen_at

            FROM users

            ORDER BY
                created_at DESC,
                id DESC
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        connection.close()


def get_user_count():

    connection = get_connection()

    try:

        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            """
        ).fetchone()

        return int(
            row["total"]
        )

    finally:

        connection.close()


def get_admin_count():

    connection = get_connection()

    try:

        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE LOWER(role) = 'admin'
            """
        ).fetchone()

        return int(
            row["total"]
        )

    finally:

        connection.close()


# ============================================================
# PASSWORD RESET FUNCTIONS
# ============================================================

def create_password_reset_token(
    user_id,
    token_hash,
    expires_at
):

    connection = get_connection()

    try:

        # Remove previous unused tokens
        connection.execute(
            """
            DELETE FROM password_reset_tokens
            WHERE user_id = ?
              AND used_at IS NULL
            """,
            (user_id,)
        )

        cursor = connection.execute(
            """
            INSERT INTO password_reset_tokens
            (
                user_id,
                token_hash,
                expires_at
            )
            VALUES
            (
                ?,
                ?,
                ?
            )
            """,
            (
                user_id,
                token_hash,
                expires_at
            )
        )

        connection.commit()

        return cursor.lastrowid

    finally:

        connection.close()


def get_password_reset_token(
    token_hash
):

    connection = get_connection()

    try:

        row = connection.execute(
            """
            SELECT
                prt.id,
                prt.user_id,
                prt.token_hash,
                prt.expires_at,
                prt.used_at,
                prt.created_at,

                users.email,
                users.name

            FROM password_reset_tokens prt

            INNER JOIN users
                ON users.id = prt.user_id

            WHERE prt.token_hash = ?

            LIMIT 1
            """,
            (token_hash,)
        ).fetchone()

        return (
            dict(row)
            if row
            else None
        )

    finally:

        connection.close()


def mark_password_reset_token_used(
    token_hash
):

    connection = get_connection()

    try:

        cursor = connection.execute(
            """
            UPDATE password_reset_tokens

            SET used_at = CURRENT_TIMESTAMP

            WHERE token_hash = ?
              AND used_at IS NULL
            """,
            (token_hash,)
        )

        connection.commit()

        return cursor.rowcount > 0

    finally:

        connection.close()


def delete_expired_password_reset_tokens():

    connection = get_connection()

    try:

        cursor = connection.execute(
            """
            DELETE FROM password_reset_tokens

            WHERE used_at IS NOT NULL

               OR datetime(expires_at)
                  < datetime('now')
            """
        )

        connection.commit()

        return cursor.rowcount

    finally:

        connection.close()


# ============================================================
# UPLOAD FUNCTIONS
# ============================================================

def create_upload(
    uploaded_by,
    title,
    source_url,
    source_type="other",
    upload_mode="mixed",
    target_module=None,
    target_category=None
):

    connection = get_connection()

    try:

        cursor = connection.execute(
            """
            INSERT INTO uploads
            (
                uploaded_by,
                title,
                source_url,
                upload_method,
                source_type,
                upload_mode,
                target_module,
                target_category,
                status
            )

            VALUES
            (
                ?,
                ?,
                ?,
                'link',
                ?,
                ?,
                ?,
                ?,
                'pending'
            )
            """,
            (
                uploaded_by,
                title,
                source_url,
                source_type,
                upload_mode,
                target_module,
                target_category
            )
        )

        connection.commit()

        return cursor.lastrowid

    finally:

        connection.close()


def get_upload(upload_id):

    connection = get_connection()

    try:

        row = connection.execute(
            """
            SELECT
                u.*,

                users.name AS uploader_name,
                users.email AS uploader_email

            FROM uploads u

            LEFT JOIN users
                ON users.id = u.uploaded_by

            WHERE u.id = ?

            LIMIT 1
            """,
            (upload_id,)
        ).fetchone()

        return (
            dict(row)
            if row
            else None
        )

    finally:

        connection.close()


def get_all_uploads():

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                u.*,

                users.name AS uploader_name,
                users.email AS uploader_email

            FROM uploads u

            LEFT JOIN users
                ON users.id = u.uploaded_by

            ORDER BY
                u.created_at DESC,
                u.id DESC
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        connection.close()


def get_user_uploads(user_id):

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT *

            FROM uploads

            WHERE uploaded_by = ?

            ORDER BY
                created_at DESC,
                id DESC
            """,
            (user_id,)
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        connection.close()


def update_upload_status(
    upload_id,
    status,
    error_message=None,
    row_count=0,
    column_count=0
):

    connection = get_connection()

    try:

        connection.execute(
            """
            UPDATE uploads

            SET
                status = ?,
                error_message = ?,
                row_count = ?,
                column_count = ?,
                updated_at = CURRENT_TIMESTAMP

            WHERE id = ?
            """,
            (
                status,
                error_message,
                row_count,
                column_count,
                upload_id
            )
        )

        connection.commit()

    finally:

        connection.close()


# ============================================================
# DATASET COLUMN FUNCTIONS
# ============================================================

def insert_column(
    upload_id,
    column_index,
    column_name,
    data_type="text"
):

    connection = get_connection()

    try:

        connection.execute(
            """
            INSERT OR REPLACE INTO dataset_columns
            (
                upload_id,
                column_index,
                column_name,
                data_type
            )

            VALUES
            (
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                upload_id,
                column_index,
                column_name,
                data_type
            )
        )

        connection.commit()

    finally:

        connection.close()


# ============================================================
# RECORD FUNCTIONS
# ============================================================

def insert_record(
    upload_id,
    module_key,
    category_key,
    sheet_name,
    row_number,
    row_data
):

    connection = get_connection()

    try:

        if isinstance(
            row_data,
            dict
        ):
            row_data = json.dumps(
                row_data,
                ensure_ascii=False,
                default=str
            )

        connection.execute(
            """
            INSERT INTO records
            (
                upload_id,
                module_key,
                category_key,
                sheet_name,
                row_number,
                row_data
            )

            VALUES
            (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                upload_id,
                module_key or "unclassified",
                category_key or "unclassified",
                sheet_name,
                row_number,
                row_data or "{}"
            )
        )

        connection.commit()

    finally:

        connection.close()


def insert_records_batch(
    records
):

    if not records:
        return

    connection = get_connection()

    try:

        prepared = []

        for record in records:

            if len(record) != 6:
                continue

            upload_id = record[0]
            module_key = (
                record[1]
                or "unclassified"
            )
            category_key = (
                record[2]
                or "unclassified"
            )
            sheet_name = record[3]
            row_number = record[4]
            row_data = record[5]

            if isinstance(
                row_data,
                dict
            ):
                row_data = json.dumps(
                    row_data,
                    ensure_ascii=False,
                    default=str
                )

            prepared.append(
                (
                    upload_id,
                    module_key,
                    category_key,
                    sheet_name,
                    row_number,
                    row_data or "{}"
                )
            )

        if prepared:

            connection.executemany(
                """
                INSERT INTO records
                (
                    upload_id,
                    module_key,
                    category_key,
                    sheet_name,
                    row_number,
                    row_data
                )

                VALUES
                (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                )
                """,
                prepared
            )

            connection.commit()

    finally:

        connection.close()


# ============================================================
# RECORD READING
# ============================================================

def _decorate_record(row):

    item = dict(row)

    try:

        data = json.loads(
            item.get(
                "row_data",
                "{}"
            )
            or "{}"
        )

    except (
        TypeError,
        ValueError
    ):

        data = {}

    if not isinstance(
        data,
        dict
    ):
        data = {}

    item["data"] = data

    # Keep row_data compatible with
    # existing templates/services.
    item["row_data"] = data

    item["module"] = item.get(
        "module_key"
    )

    item["category"] = item.get(
        "category_key"
    )

    item["filename"] = item.get(
        "title"
    )

    item["uploader"] = item.get(
        "uploader_name"
    )

    return item


def get_records_for_module(
    module_key,
    category_key=None
):

    connection = get_connection()

    try:

        query = """
            SELECT
                r.*,
                u.title,
                u.source_url,
                u.uploaded_by,

                users.name AS uploader_name,
                users.email AS uploader_email

            FROM records r

            INNER JOIN uploads u
                ON u.id = r.upload_id

            LEFT JOIN users
                ON users.id = u.uploaded_by

            WHERE r.module_key = ?
        """

        params = [
            module_key
        ]

        if category_key:

            query += """
                AND r.category_key = ?
            """

            params.append(
                category_key
            )

        query += """
            ORDER BY
                r.created_at DESC,
                r.row_number
        """

        rows = connection.execute(
            query,
            params
        ).fetchall()

        return [
            _decorate_record(row)
            for row in rows
        ]

    finally:

        connection.close()


def get_all_records():

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                r.*,

                u.title,
                u.source_url,
                u.uploaded_by,

                users.name AS uploader_name,
                users.email AS uploader_email

            FROM records r

            INNER JOIN uploads u
                ON u.id = r.upload_id

            LEFT JOIN users
                ON users.id = u.uploaded_by

            ORDER BY
                r.module_key,
                r.category_key,
                u.created_at DESC,
                r.row_number
            """
        ).fetchall()

        return [
            _decorate_record(row)
            for row in rows
        ]

    finally:

        connection.close()


def get_all_rows(
    module=None,
    category=None,
    upload_id=None,
    user_id=None
):

    connection = get_connection()

    try:

        query = """
            SELECT
                r.*,

                u.title,
                u.source_url,
                u.uploaded_by,

                users.name AS uploader_name,
                users.email AS uploader_email

            FROM records r

            INNER JOIN uploads u
                ON u.id = r.upload_id

            LEFT JOIN users
                ON users.id = u.uploaded_by

            WHERE 1 = 1
        """

        params = []

        if module:

            query += """
                AND r.module_key = ?
            """

            params.append(
                module
            )

        if category:

            query += """
                AND r.category_key = ?
            """

            params.append(
                category
            )

        if upload_id is not None:

            query += """
                AND r.upload_id = ?
            """

            params.append(
                upload_id
            )

        if user_id is not None:

            query += """
                AND u.uploaded_by = ?
            """

            params.append(
                user_id
            )

        query += """
            ORDER BY
                r.created_at DESC,
                r.row_number
        """

        rows = connection.execute(
            query,
            params
        ).fetchall()

        return [
            _decorate_record(row)
            for row in rows
        ]

    finally:

        connection.close()


def get_module_statistics():

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                module_key,
                category_key,
                COUNT(*) AS total

            FROM records

            GROUP BY
                module_key,
                category_key

            ORDER BY
                module_key,
                category_key
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        connection.close()


# ============================================================
# DELETE FUNCTIONS
# ============================================================

def delete_upload_records(
    upload_id
):

    connection = get_connection()

    try:

        connection.execute(
            """
            DELETE FROM records
            WHERE upload_id = ?
            """,
            (upload_id,)
        )

        connection.execute(
            """
            DELETE FROM dataset_columns
            WHERE upload_id = ?
            """,
            (upload_id,)
        )

        connection.execute(
            """
            DELETE FROM dataset_refresh_logs
            WHERE upload_id = ?
            """,
            (upload_id,)
        )

        connection.commit()

    finally:

        connection.close()


def delete_upload(
    upload_id
):

    connection = get_connection()

    try:

        # Because records/dataset_columns/
        # refresh_logs use ON DELETE CASCADE,
        # deleting the upload removes its data too.

        cursor = connection.execute(
            """
            DELETE FROM uploads
            WHERE id = ?
            """,
            (upload_id,)
        )

        connection.commit()

        return cursor.rowcount > 0

    finally:

        connection.close()


def delete_user_upload(
    upload_id,
    user_id
):

    connection = get_connection()

    try:

        cursor = connection.execute(
            """
            DELETE FROM uploads

            WHERE id = ?
              AND uploaded_by = ?
            """,
            (
                upload_id,
                user_id
            )
        )

        connection.commit()

        return cursor.rowcount > 0

    finally:

        connection.close()


# ============================================================
# ADMIN STATISTICS
# ============================================================

def get_user_statistics():

    connection = get_connection()

    try:

        total_users = connection.execute(
            """
            SELECT COUNT(*)
            FROM users
            """
        ).fetchone()[0]

        total_admins = connection.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE LOWER(role) = 'admin'
            """
        ).fetchone()[0]

        total_regular_users = connection.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE LOWER(role) = 'user'
            """
        ).fetchone()[0]

        total_uploads = connection.execute(
            """
            SELECT COUNT(*)
            FROM uploads
            """
        ).fetchone()[0]

        total_records = connection.execute(
            """
            SELECT COUNT(*)
            FROM records
            """
        ).fetchone()[0]

        return {
            "total_users": total_users,
            "total_admins": total_admins,
            "total_regular_users": total_regular_users,
            "total_uploads": total_uploads,
            "total_records": total_records,
        }

    finally:

        connection.close()


def print_user_statistics():

    stats = get_user_statistics()

    print()
    print("=" * 55)
    print("UCE_CONNECT DATABASE STATISTICS")
    print("=" * 55)
    print(
        f"Total Users        : "
        f"{stats['total_users']}"
    )
    print(
        f"Total Admins       : "
        f"{stats['total_admins']}"
    )
    print(
        f"Regular Users      : "
        f"{stats['total_regular_users']}"
    )
    print(
        f"Total Submissions  : "
        f"{stats['total_uploads']}"
    )
    print(
        f"Total Data Records : "
        f"{stats['total_records']}"
    )
    print("=" * 55)
    print()


# ============================================================
# AUTO INITIALIZATION
# ============================================================

# Do not automatically initialize during import.
# app.py should call init_database() once while starting.

if __name__ == "__main__":

    init_database()

    print(
        "UCE_Connect database initialized successfully."
    )

    print_user_statistics()