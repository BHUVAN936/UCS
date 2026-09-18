import os
import secrets
from pathlib import Path


BASE_DIR = Path(
    __file__
).resolve().parent


class Config:

    # Set UCE_SECRET_KEY in production. A random development key is used
    # when the environment variable is not configured.
    SECRET_KEY = os.getenv("UCE_SECRET_KEY") or secrets.token_hex(32)

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

    # -----------------------------------------------------
    # PASSWORD RESET
    # -----------------------------------------------------

    PASSWORD_RESET_MINUTES = int(
        os.getenv(
            "UCE_PASSWORD_RESET_MINUTES",
            "30",
        )
    )

    # Keep False so reset tokens are never displayed in the normal UI.
    # Enable only for local development if email delivery is unavailable.
    EXPOSE_RESET_LINKS = (
        os.getenv(
            "UCE_EXPOSE_RESET_LINKS",
            "false",
        ).lower()
        == "true"
    )

    # -----------------------------------------------------
    # PASSWORD RESET EMAIL
    # -----------------------------------------------------
    # Configure these environment variables before using
    # password reset in a deployed application.

    SMTP_HOST = os.getenv(
        "UCE_SMTP_HOST",
        "",
    )

    SMTP_PORT = int(
        os.getenv(
            "UCE_SMTP_PORT",
            "587",
        )
    )

    SMTP_USERNAME = os.getenv(
        "UCE_SMTP_USERNAME",
        "",
    )

    SMTP_PASSWORD = os.getenv(
        "UCE_SMTP_PASSWORD",
        "",
    )

    SMTP_USE_TLS = (
        os.getenv(
            "UCE_SMTP_USE_TLS",
            "true",
        ).lower()
        == "true"
    )

    SMTP_USE_SSL = (
        os.getenv(
            "UCE_SMTP_USE_SSL",
            "false",
        ).lower()
        == "true"
    )

    SMTP_FROM_EMAIL = os.getenv(
        "UCE_SMTP_FROM_EMAIL",
        SMTP_USERNAME,
    )
