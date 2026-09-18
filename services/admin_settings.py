import secrets
import sqlite3
from pathlib import Path

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)


# ============================================================
# DATABASE LOCATION
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

DATABASE_PATH = (
    BASE_DIR
    / "instance"
    / "database.db"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        str(DATABASE_PATH)
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# CREATE SETTINGS TABLE
# ============================================================

def initialize_settings():

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                setting_key TEXT NOT NULL UNIQUE,

                setting_value TEXT,

                created_at TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TIMESTAMP
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.commit()

    finally:

        connection.close()


# ============================================================
# GET SETTING
# ============================================================

def get_setting(key):

    initialize_settings()

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT setting_value
            FROM app_settings
            WHERE setting_key = ?
            """,
            (key,),
        )

        row = cursor.fetchone()

        if row:

            return row["setting_value"]

        return None

    finally:

        connection.close()


# ============================================================
# SAVE SETTING
# ============================================================

def save_setting(
    key,
    value,
):

    initialize_settings()

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO app_settings
            (
                setting_key,
                setting_value
            )
            VALUES (?, ?)

            ON CONFLICT(setting_key)
            DO UPDATE SET
                setting_value = excluded.setting_value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                key,
                value,
            ),
        )

        connection.commit()

    finally:

        connection.close()


# ============================================================
# INITIAL ADMIN CODE
# ============================================================

def ensure_admin_registration_code():

    initialize_settings()

    existing_hash = get_setting(
        "admin_registration_code"
    )

    # --------------------------------------------------------
    # If code already exists, do nothing.
    # --------------------------------------------------------

    if existing_hash:

        return

    # --------------------------------------------------------
    # First-time default code.
    #
    # IMPORTANT:
    # This is used ONLY when the database does not yet have
    # an admin registration code.
    #
    # After the first generated/changed code, the database
    # value is used.
    # --------------------------------------------------------

    initial_code = "Bhuvan@25"

    hashed_code = generate_password_hash(
        initial_code
    )

    save_setting(
        "admin_registration_code",
        hashed_code,
    )


# ============================================================
# VERIFY ADMIN REGISTRATION CODE
# ============================================================

def verify_admin_registration_code(
    code,
):

    if not code:

        return False

    ensure_admin_registration_code()

    stored_hash = get_setting(
        "admin_registration_code"
    )

    if not stored_hash:

        return False

    try:

        return check_password_hash(
            stored_hash,
            code,
        )

    except Exception:

        return False


# ============================================================
# GENERATE NEW ADMIN REGISTRATION CODE
# ============================================================

def generate_admin_registration_code():

    # --------------------------------------------------------
    # Generate a random code.
    #
    # Example:
    # UCE-A3F2-91BC
    # --------------------------------------------------------

    part_one = secrets.token_hex(
        2
    ).upper()

    part_two = secrets.token_hex(
        2
    ).upper()

    new_code = (
        f"UCE-{part_one}-{part_two}"
    )

    # --------------------------------------------------------
    # Store ONLY the hash.
    # --------------------------------------------------------

    hashed_code = generate_password_hash(
        new_code
    )

    save_setting(
        "admin_registration_code",
        hashed_code,
    )

    # --------------------------------------------------------
    # Return the actual code once so the admin can copy it.
    # --------------------------------------------------------

    return new_code