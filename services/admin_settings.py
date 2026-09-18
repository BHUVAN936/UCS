import os
import secrets

from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)

from database.db import get_connection


# ============================================================
# DATABASE SETTINGS
# ============================================================
# database/db.py is the single owner of the database connection
# and database initialization.
#
# This file only reads/writes settings through get_connection().
# It does NOT create app_settings again.
# ============================================================


# ============================================================
# INITIALIZE SETTINGS
# ============================================================

def initialize_settings():
    """
    Compatibility function for existing code that calls
    initialize_settings().

    The app_settings table is created by database/db.py/schema.sql.
    Keeping this function avoids breaking existing callers while
    preventing duplicate table creation.
    """
    return None


# ============================================================
# GET SETTING
# ============================================================

def get_setting(key):

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
# GENERATE RANDOM ADMIN REGISTRATION CODE
# ============================================================

def _generate_random_admin_code():

    part_one = secrets.token_hex(
        2
    ).upper()

    part_two = secrets.token_hex(
        2
    ).upper()

    return (
        f"UCE-{part_one}-{part_two}"
    )


# ============================================================
# INITIAL ADMIN CODE
# ============================================================

def ensure_admin_registration_code():

    existing_hash = get_setting(
        "admin_registration_code"
    )

    # --------------------------------------------------------
    # If a code already exists, never replace it.
    # --------------------------------------------------------

    if existing_hash:

        return

    # --------------------------------------------------------
    # First priority:
    # Use administrator-provided environment variable.
    #
    # PowerShell:
    #
    # $env:UCE_ADMIN_REGISTRATION_CODE="YourCodeHere"
    # --------------------------------------------------------

    configured_code = os.getenv(
        "UCE_ADMIN_REGISTRATION_CODE"
    )

    if configured_code:

        initial_code = configured_code

        print(
            "\nUCE Connect admin registration code "
            "loaded from UCE_ADMIN_REGISTRATION_CODE."
        )

    else:

        # ----------------------------------------------------
        # No hardcoded secret.
        # Generate a secure random first-time code.
        # ----------------------------------------------------

        initial_code = _generate_random_admin_code()

        print(
            "\n"
            "====================================================\n"
            "UCE CONNECT - INITIAL ADMIN REGISTRATION CODE\n"
            "====================================================\n"
            f"{initial_code}\n"
            "Save this code securely. It will not be shown again.\n"
            "====================================================\n"
        )

    # --------------------------------------------------------
    # Store ONLY the hash in the database.
    # --------------------------------------------------------

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
    # Generate a new random code.
    #
    # Example:
    # UCE-A3F2-91BC
    # --------------------------------------------------------

    new_code = _generate_random_admin_code()

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
