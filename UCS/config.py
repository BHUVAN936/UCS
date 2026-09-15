import os


class Config:
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "uce-connect-development-key"
    )

    DATABASE = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "instance",
        "database.db"
    )

    PROJECT_NAME = "UCE Connect"
    PROJECT_TAGLINE = "University Information Portal"