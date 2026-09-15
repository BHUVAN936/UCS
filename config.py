import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:

    SECRET_KEY = os.getenv(
        "UCE_SECRET_KEY",
        "uce-connect-development-secret-change-this"
    )

    DATABASE_PATH = str(
        BASE_DIR / "instance" / "database.db"
    )

    UPLOAD_FOLDER = str(
        BASE_DIR / "instance" / "uploads"
    )

    MAX_CONTENT_LENGTH = 25 * 1024 * 1024

    ALLOWED_EXTENSIONS = {
        "csv",
        "xlsx",
        "xls"
    }

    ADMIN_REGISTRATION_CODE = os.getenv(
        "UCE_ADMIN_REGISTRATION_CODE",
        "Bhuvan@25"
    )

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False