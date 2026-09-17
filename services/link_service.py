
import ipaddress
import re
import socket
import tempfile

from pathlib import Path
from urllib.parse import (
    parse_qs,
    urlencode,
    urlparse,
)

import requests


MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024

TIMEOUT = (
    10,
    60
)

ALLOWED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
}


class LinkDownloadError(ValueError):
    pass


# =========================================================
# SECURITY
# =========================================================

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
        "metadata.google.internal",
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
        (url or "").strip()
    )

    if parsed.scheme not in {
        "http",
        "https",
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


# =========================================================
# GOOGLE
# =========================================================

def google_drive_file_id(url):

    patterns = [
        r"/file/d/([A-Za-z0-9_-]+)",
        r"/open\?id=([A-Za-z0-9_-]+)",
        r"[?&]id=([A-Za-z0-9_-]+)",
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


# =========================================================
# ONEDRIVE
# =========================================================

def is_onedrive_url(url):

    host = (
        urlparse(url)
        .hostname
        or ""
    ).lower()

    return (
        host == "1drv.ms"
        or host.endswith(".1drv.ms")
        or host == "onedrive.live.com"
        or host.endswith(".onedrive.live.com")
    )


def build_onedrive_download_url(url):

    """
    Microsoft sharing links normally redirect to a public
    OneDrive page. Following that redirect is allowed, but
    the direct download endpoint is preferred when available.
    """

    parsed = urlparse(url)

    query = parse_qs(
        parsed.query
    )

    # Existing download=1 links
    if query.get(
        "download"
    ) == ["1"]:
        return url

    separator = "&" if parsed.query else "?"

    return (
        url
        + separator
        + "download=1"
    )


# =========================================================
# BUILD DOWNLOAD URL
# =========================================================

def build_download_url(url):

    parsed = validate_url(url)

    host = (
        parsed.hostname
        or ""
    ).lower()

    if is_onedrive_url(url):

        return build_onedrive_download_url(
            url
        )

    drive_id = google_drive_file_id(
        url
    )

    if (
        drive_id
        and host in {
            "drive.google.com",
            "docs.google.com",
        }
    ):

        # Google Drive's usercontent endpoint is more reliable for
        # publicly shared files than treating the sharing page as
        # the downloadable file.
        return (
            "https://drive.usercontent.google.com/download?"
            + urlencode(
                {
                    "id": drive_id,
                    "export": "download",
                    "confirm": "t",
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
            "https://docs.google.com/spreadsheets/d/"
            f"{sheet_id}/export?format=xlsx"
        )

    return url


# =========================================================
# FILE DETECTION
# =========================================================

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
        data[:1000]
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
        .get(
            "Content-Type",
            ""
        )
        .lower()
    )

    if (
        "spreadsheetml" in content_type
        or "openxmlformats" in content_type
    ):
        return ".xlsx"

    if (
        "ms-excel" in content_type
        or "application/excel" in content_type
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

        # OneDrive can occasionally return a page even
        # when download=1 is supplied.
        if is_onedrive_url(
            requested_url
        ):

            raise LinkDownloadError(
                "OneDrive returned a webpage instead of the "
                "spreadsheet. Make sure the file is shared "
                "publicly and download permission is enabled."
            )

        raise LinkDownloadError(
            "The link returned a webpage instead of a "
            "spreadsheet. Make sure the file is publicly shared."
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
        "The link does not appear to contain a supported "
        "CSV, XLS or XLSX file."
    )


# =========================================================
# DOWNLOAD
# =========================================================

def download_spreadsheet(url):

    original = validate_url(
        url
    )

    download_url = build_download_url(
        url
    )

    headers = {
        "User-Agent":
            "Mozilla/5.0 UCE-Connect/1.0",
        "Accept":
            "*/*",
    }

    try:

        # -----------------------------------------------------
        # FIRST REQUEST
        # -----------------------------------------------------

        response = requests.get(
            download_url,
            headers=headers,
            stream=True,
            allow_redirects=True,
            timeout=TIMEOUT,
        )

        response.raise_for_status()

        validate_url(
            response.url
        )

        # -----------------------------------------------------
        # GOOGLE DRIVE FALLBACK
        # -----------------------------------------------------
        # Some public Drive files can still return an HTML
        # confirmation/permission page from the first endpoint.
        # Retry with the classic uc?export=download endpoint.
        # -----------------------------------------------------

        if (
            _looks_like_html(
                response.content[:4096]
            )
            and
            google_drive_file_id(
                original.geturl()
            )
        ):

            response.close()

            drive_id = google_drive_file_id(
                original.geturl()
            )

            fallback_url = (
                "https://drive.google.com/uc?"
                + urlencode(
                    {
                        "export": "download",
                        "id": drive_id,
                        "confirm": "t",
                    }
                )
            )

            response = requests.get(
                fallback_url,
                headers=headers,
                stream=True,
                allow_redirects=True,
                timeout=TIMEOUT,
            )

            response.raise_for_status()

            validate_url(
                response.url
            )

        # -----------------------------------------------------
        # SIZE CHECK
        # -----------------------------------------------------

        content_length = (
            response.headers.get(
                "Content-Length"
            )
        )

        if content_length:

            try:

                if (
                    int(content_length)
                    > MAX_DOWNLOAD_BYTES
                ):
                    response.close()

                    raise LinkDownloadError(
                        "The spreadsheet is larger than "
                        "the 25 MB limit."
                    )

            except ValueError:
                pass

        # -----------------------------------------------------
        # WRITE TEMPORARY FILE
        # -----------------------------------------------------

        first_chunk = b""
        total = 0

        temporary = tempfile.NamedTemporaryFile(
            prefix="uce-link-",
            suffix=".download",
            delete=False,
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
                    first_chunk = chunk[:4096]

                total += len(chunk)

                if (
                    total
                    > MAX_DOWNLOAD_BYTES
                ):

                    raise LinkDownloadError(
                        "The spreadsheet is larger than "
                        "the 25 MB limit."
                    )

                temporary.write(
                    chunk
                )

            temporary.close()
            response.close()

            if total == 0:

                raise LinkDownloadError(
                    "The link returned an empty file."
                )

            # -------------------------------------------------
            # VERIFY THAT IT IS ACTUALLY A SPREADSHEET
            # -------------------------------------------------

            extension = _detect_extension(
                first_chunk,
                response,
                response.url or original.geturl(),
            )

            final_path = temp_path.with_suffix(
                extension
            )

            temp_path.rename(
                final_path
            )

            filename = Path(
                urlparse(
                    response.url
                    or original.geturl()
                ).path
            ).name

            if (
                not filename
                or Path(
                    filename
                ).suffix.lower()
                not in ALLOWED_EXTENSIONS
            ):

                filename = (
                    "linked-spreadsheet"
                    + extension
                )

            return (
                final_path,
                filename,
            )

        except Exception:

            try:
                temporary.close()
            except Exception:
                pass

            try:
                response.close()
            except Exception:
                pass

            temp_path.unlink(
                missing_ok=True
            )

            raise

    except requests.RequestException as error:

        raise LinkDownloadError(
            "Could not download the spreadsheet. "
            "Make sure the link is publicly accessible "
            "and the file can be downloaded without signing in."
        ) from error
