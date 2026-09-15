import ipaddress
import re
import socket
import tempfile

from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests


MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024

TIMEOUT = (
    10,
    60
)

ALLOWED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls"
}


class LinkDownloadError(ValueError):
    pass


def _validate_public_host(hostname):

    if not hostname:

        raise LinkDownloadError(
            "The link must contain a valid hostname."
        )

    hostname = hostname.lower().rstrip(".")

    blocked = {
        "localhost",
        "localhost.localdomain",
        "metadata",
        "metadata.google.internal"
    }

    if (
        hostname in blocked
        or hostname.endswith(".local")
    ):

        raise LinkDownloadError(
            "Private/local network links are not allowed."
        )

    try:

        addresses = socket.getaddrinfo(
            hostname,
            None
        )

    except socket.gaierror as error:

        raise LinkDownloadError(
            "The link hostname could not be resolved."
        ) from error

    for address in addresses:

        ip_text = address[4][0]

        ip = ipaddress.ip_address(
            ip_text
        )

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):

            raise LinkDownloadError(
                "Links to private or local networks are not allowed."
            )


def validate_url(url):

    parsed = urlparse(
        url.strip()
    )

    if parsed.scheme not in {
        "http",
        "https"
    }:

        raise LinkDownloadError(
            "Only HTTP and HTTPS links are supported."
        )

    if parsed.username or parsed.password:

        raise LinkDownloadError(
            "Links containing embedded credentials are not allowed."
        )

    _validate_public_host(
        parsed.hostname
    )

    return parsed


def google_drive_file_id(url):

    patterns = [

        r"/file/d/([A-Za-z0-9_-]+)",

        r"/open\?id=([A-Za-z0-9_-]+)",

        r"[?&]id=([A-Za-z0-9_-]+)"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            url
        )

        if match:

            return match.group(1)

    return None


def google_sheets_id(url):

    match = re.search(
        r"/spreadsheets/d/([A-Za-z0-9_-]+)",
        url
    )

    if match:

        return match.group(1)

    return None


def build_download_url(url):

    parsed = validate_url(url)

    host = (
        parsed.hostname
        or ""
    ).lower()

    drive_id = google_drive_file_id(
        url
    )

    if (
        drive_id
        and host in {
            "drive.google.com",
            "docs.google.com"
        }
    ):

        return (
            "https://drive.usercontent.google.com/download?"
            +
            urlencode(
                {
                    "id": drive_id,
                    "export": "download"
                }
            )
        )

    sheet_id = google_sheets_id(
        url
    )

    if (
        sheet_id
        and host == "docs.google.com"
    ):

        return (
            f"https://docs.google.com/spreadsheets/d/"
            f"{sheet_id}/export?format=xlsx"
        )

    return url


def _looks_like_xlsx(data):

    return data.startswith(
        b"PK\x03\x04"
    )


def _looks_like_xls(data):

    return data.startswith(
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    )


def _looks_like_html(data):

    sample = (
        data[:500]
        .lstrip()
        .lower()
    )

    return (
        sample.startswith(b"<!doctype html")
        or sample.startswith(b"<html")
        or b"<head" in sample
    )


def _detect_extension(
    first_bytes,
    response,
    requested_url
):

    path_suffix = Path(
        urlparse(
            requested_url
        ).path
    ).suffix.lower()

    if path_suffix in ALLOWED_EXTENSIONS:

        return path_suffix

    content_type = (
        response.headers
        .get("Content-Type", "")
        .lower()
    )

    if "spreadsheetml" in content_type:

        return ".xlsx"

    if (
        "ms-excel" in content_type
        or "excel" in content_type
    ):

        return ".xls"

    if (
        "csv" in content_type
        or "text/plain" in content_type
    ):

        return ".csv"

    if _looks_like_xlsx(
        first_bytes
    ):

        return ".xlsx"

    if _looks_like_xls(
        first_bytes
    ):

        return ".xls"

    if _looks_like_html(
        first_bytes
    ):

        raise LinkDownloadError(
            "The link returned a web page instead of "
            "a spreadsheet. Make sure the Google file "
            "is shared publicly."
        )

    try:

        text = first_bytes.decode(
            "utf-8-sig",
            errors="ignore"
        )

        if (
            "," in text
            or "\t" in text
        ):

            return ".csv"

    except Exception:

        pass

    raise LinkDownloadError(
        "The link does not appear to contain "
        "a supported CSV, XLS or XLSX file."
    )


def download_spreadsheet(url):

    original = validate_url(
        url
    )

    download_url = build_download_url(
        url
    )

    validate_url(
        download_url
    )

    headers = {
        "User-Agent":
            "UCE-Connect/1.0",
        "Accept":
            "*/*"
    }

    try:

        with requests.get(
            download_url,
            headers=headers,
            stream=True,
            allow_redirects=True,
            timeout=TIMEOUT
        ) as response:

            response.raise_for_status()

            validate_url(
                response.url
            )

            content_length = response.headers.get(
                "Content-Length"
            )

            if content_length:

                try:

                    if (
                        int(content_length)
                        > MAX_DOWNLOAD_BYTES
                    ):

                        raise LinkDownloadError(
                            "The spreadsheet is larger "
                            "than the 25 MB limit."
                        )

                except ValueError:

                    pass

            first_chunk = b""

            total = 0

            temporary = tempfile.NamedTemporaryFile(
                prefix="uce-link-",
                suffix=".download",
                delete=False
            )

            temp_path = Path(
                temporary.name
            )

            try:

                for chunk in response.iter_content(
                    chunk_size=64 * 1024
                ):

                    if not chunk:
                        continue

                    if not first_chunk:

                        first_chunk = chunk[:2048]

                    total += len(chunk)

                    if (
                        total
                        > MAX_DOWNLOAD_BYTES
                    ):

                        raise LinkDownloadError(
                            "The spreadsheet is larger "
                            "than the 25 MB limit."
                        )

                    temporary.write(
                        chunk
                    )

                temporary.close()

                if total == 0:

                    raise LinkDownloadError(
                        "The link returned an empty file."
                    )

                extension = _detect_extension(
                    first_chunk,
                    response,
                    original.geturl()
                )

                final_path = (
                    temp_path.with_suffix(
                        extension
                    )
                )

                temp_path.rename(
                    final_path
                )

                filename = Path(
                    urlparse(
                        original.geturl()
                    ).path
                ).name

                if (
                    not filename
                    or Path(filename).suffix.lower()
                    not in ALLOWED_EXTENSIONS
                ):

                    filename = (
                        "linked-spreadsheet"
                        + extension
                    )

                return (
                    final_path,
                    filename
                )

            except Exception:

                temporary.close()

                temp_path.unlink(
                    missing_ok=True
                )

                raise

    except requests.RequestException as error:

        raise LinkDownloadError(
            "Could not download the spreadsheet. "
            "Check that the link is public and accessible."
        ) from error