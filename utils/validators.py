from pathlib import Path


ALLOWED_EXTENSIONS = {
    "csv",
    "xlsx",
    "xls",
    "pdf"
}


def allowed_file(filename):

    if not filename:

        return False

    extension = (
        Path(filename)
        .suffix
        .lower()
        .replace(
            ".",
            ""
        )
    )

    return extension in ALLOWED_EXTENSIONS


def valid_username(username):

    if not username:
        return False

    username = username.strip()

    if len(username) < 3:
        return False

    if " " in username:
        return False

    return True


def valid_password(password):

    if not password:
        return False

    return len(password) >= 6


def valid_email(email):

    if not email:
        return False

    email = email.strip()

    return (
        "@" in email
        and "." in email.split("@")[-1]
    )