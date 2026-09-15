from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:

    SECRET_KEY = "uce-connect-development-key"

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    ALLOWED_EXTENSIONS = {
        "csv",
        "xlsx",
        "xls",
        "pdf"
    }