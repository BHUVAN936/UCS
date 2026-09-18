import os
from pathlib import Path


BASE_DIR = Path(
    __file__
).resolve().parent


class Config:

    SECRET_KEY = os.getenv(
        "UCE_SECRET_KEY",
        "uce-connect-development-secret-change-this",
    )

    DATABASE_PATH = str(
        BASE_DIR
        / "instance"
        / "database.db"
    )

    UPLOAD_FOLDER = str(
        BASE_DIR
        / "instance"
        / "uploads"
    )

    MAX_CONTENT_LENGTH = (
        25 * 1024 * 1024
    )

    ALLOWED_EXTENSIONS = {
        "csv",
        "xlsx",
        "xls",
    }

    SESSION_COOKIE_HTTPONLY = True

    SESSION_COOKIE_SAMESITE = "Lax"

    # Keep False for localhost development.
    # Set UCE_COOKIE_SECURE=true when deployed with HTTPS.
    SESSION_COOKIE_SECURE = (
        os.getenv(
            "UCE_COOKIE_SECURE",
            "false",
        ).lower()
        == "true"
    )

    SESSION_COOKIE_NAME = "uce_session"

    SEND_FILE_MAX_AGE_DEFAULT = 0