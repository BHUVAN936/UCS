
import ipaddress
import re
import socket
import tempfile

from pathlib import Path
from urllib.parse import (
    parse_qs,
    urlencode,
    urlparse,
    urljoin,
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
# SAFE HTTP DOWNLOAD
# =========================================================

MAX_REDIRECTS = 5
MAX_HTML_INSPECTION_BYTES = 2 * 1024 * 1024


def _safe_get(session, url, headers):
    """
    Download one HTTP response while validating every redirect before the
    next network connection is made. Automatic redirects are disabled so a
    public URL cannot silently redirect the server to a private address.
    """
    current_url = validate_url(url).geturl()

    for _ in range(MAX_REDIRECTS + 1):
        validate_url(current_url)

        response = session.get(
            current_url,
            headers=headers,
            stream=True,
            allow_redirects=False,
            timeout=TIMEOUT,
        )

        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            if not location:
                response.close()
                raise LinkDownloadError("The server returned an invalid redirect.")

            next_url = urljoin(current_url, location)
            response.close()

            # Validate BEFORE connecting to the redirect destination.
            validate_url(next_url)
            current_url = next_url
            continue

        response.raise_for_status()
        return response, current_url

    raise LinkDownloadError("The spreadsheet link redirected too many times.")


def _content_length_is_too_large(response):
    value = response.headers.get("Content-Length")
    if not value:
        return False

    try:
        return int(value) > MAX_DOWNLOAD_BYTES
    except (TypeError, ValueError):
        return False


def _stream_response_to_file(response):
    """
    Stream the response to disk with a hard 25 MB limit.

    No response.content/read() is used, so the complete response is never
    loaded into memory.
    """
    if _content_length_is_too_large(response):
        raise LinkDownloadError("The spreadsheet is larger than the 25 MB limit.")

    temporary = tempfile.NamedTemporaryFile(
        prefix="uce-link-",
        suffix=".download",
        delete=False,
    )
    temp_path = Path(temporary.name)

    total = 0
    first_bytes = bytearray()

    try:
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue

            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                raise LinkDownloadError(
                    "The spreadsheet is larger than the 25 MB limit."
                )

            if len(first_bytes) < 4096:
                first_bytes.extend(chunk[: 4096 - len(first_bytes)])

            temporary.write(chunk)

        temporary.flush()
        temporary.close()
        temporary = None

        if total == 0:
            temp_path.unlink(missing_ok=True)
            raise LinkDownloadError("The link returned an empty file.")

        return temp_path, bytes(first_bytes), total

    except Exception:
        try:
            temporary.close()
        except Exception:
            pass
        temp_path.unlink(missing_ok=True)
        raise


def _read_bounded_file(path, limit=MAX_HTML_INSPECTION_BYTES):
    """Read only a bounded amount from a temporary HTML response."""
    with path.open("rb") as file:
        return file.read(limit)


def _extract_html_input(html_bytes, name):
    """Extract a hidden/form input value without requiring BeautifulSoup."""
    text = html_bytes.decode("utf-8", errors="ignore")

    patterns = [
        rf'<input[^>]+name=["\']{re.escape(name)}["\'][^>]+value=["\']([^"\']*)["\']',
        rf'<input[^>]+value=["\']([^"\']*)["\'][^>]+name=["\']{re.escape(name)}["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def _google_drive_resource_key(url):
    try:
        query = parse_qs(urlparse(url).query)
        value = query.get("resourcekey")
        return value[0] if value else None
    except Exception:
        return None


def _build_google_drive_confirmation_url(original_url, html_bytes):
    """
    Build a second Google Drive download request from the confirmation page.

    Large/public Drive files can return a small HTML warning/confirmation
    page. The confirmation token (and sometimes uuid) must be sent back with
    the request. Resource keys are also preserved when the original share URL
    contains one.
    """
    drive_id = google_drive_file_id(original_url)
    if not drive_id:
        return None

    confirm = _extract_html_input(html_bytes, "confirm")
    uuid = _extract_html_input(html_bytes, "uuid")
    acknowledge = _extract_html_input(html_bytes, "acknowledgeAbuse")

    # Google sometimes exposes the confirmation value in a download link
    # instead of a hidden input.
    if not confirm:
        text = html_bytes.decode("utf-8", errors="ignore")
        match = re.search(r"[?&]confirm=([^&\"'<>]+)", text, re.IGNORECASE)
        if match:
            confirm = match.group(1)

    params = {
        "export": "download",
        "id": drive_id,
    }

    if confirm:
        params["confirm"] = confirm
    else:
        # Works for the common Drive confirmation flow even when no hidden
        # token is exposed in the first HTML page.
        params["confirm"] = "t"

    if uuid:
        params["uuid"] = uuid

    if acknowledge:
        params["acknowledgeAbuse"] = acknowledge

    resource_key = _google_drive_resource_key(original_url)
    if resource_key:
        params["resourcekey"] = resource_key

    # usercontent is preferred; Google may redirect it to the actual file.
    return "https://drive.usercontent.google.com/download?" + urlencode(params)


def _google_drive_classic_url(original_url, html_bytes=None):
    """Build the classic Drive /uc download URL as a final fallback."""
    drive_id = google_drive_file_id(original_url)
    if not drive_id:
        return None

    params = {
        "export": "download",
        "id": drive_id,
        "confirm": "t",
    }

    resource_key = _google_drive_resource_key(original_url)
    if resource_key:
        params["resourcekey"] = resource_key

    if html_bytes:
        uuid = _extract_html_input(html_bytes, "uuid")
        if uuid:
            params["uuid"] = uuid

    return "https://drive.google.com/uc?" + urlencode(params)


def _filename_from_response(response, final_url, extension):
    """Prefer a safe filename supplied by the server, then URL filename."""
    disposition = response.headers.get("Content-Disposition", "")
    match = re.search(
        r"filename\*?=(?:UTF-8''|\"|')?([^\"';\r\n]+)",
        disposition,
        flags=re.IGNORECASE,
    )

    if match:
        candidate = Path(match.group(1).strip()).name
        if candidate:
            candidate_ext = Path(candidate).suffix.lower()
            if candidate_ext in ALLOWED_EXTENSIONS:
                return candidate

    filename = Path(urlparse(final_url).path).name
    if filename and Path(filename).suffix.lower() in ALLOWED_EXTENSIONS:
        return filename

    return "linked-spreadsheet" + extension


# =========================================================
# DOWNLOAD
# =========================================================

def download_spreadsheet(url):
    """
    Download a public CSV/XLS/XLSX file from a normal URL, Google Drive,
    Google Sheets or OneDrive.

    Important Google Drive behavior:
    a public Drive file may first return an HTML confirmation page. We detect
    that page BEFORE rejecting it, extract the confirmation information, and
    retry the actual download.
    """
    original = validate_url(url)
    original_url = original.geturl()
    download_url = build_download_url(original_url)

    # Validate generated URLs too.
    validate_url(download_url)

    headers = {
        "User-Agent": "Mozilla/5.0 UCE-Connect/1.0",
        "Accept": "text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*",
    }

    session = requests.Session()
    response = None
    temp_path = None

    try:
        # ---------------------------------------------------------
        # FIRST REQUEST
        # ---------------------------------------------------------
        response, final_url = _safe_get(
            session,
            download_url,
            headers,
        )

        temp_path, first_bytes, _ = _stream_response_to_file(response)

        # ---------------------------------------------------------
        # GOOGLE DRIVE CONFIRMATION HANDLING
        # ---------------------------------------------------------
        # DO THIS BEFORE _detect_extension(), because _detect_extension()
        # intentionally rejects HTML pages.
        if (
            _looks_like_html(first_bytes)
            and google_drive_file_id(original_url)
        ):
            html_bytes = _read_bounded_file(temp_path)

            response.close()
            response = None
            temp_path.unlink(missing_ok=True)
            temp_path = None

            # Attempt 1: confirmation token from Google's HTML.
            confirmation_url = _build_google_drive_confirmation_url(
                original_url,
                html_bytes,
            )

            if confirmation_url:
                response, final_url = _safe_get(
                    session,
                    confirmation_url,
                    headers,
                )
                temp_path, first_bytes, _ = _stream_response_to_file(response)

            # Attempt 2: classic /uc endpoint if Google still returned HTML.
            if _looks_like_html(first_bytes):
                html_bytes_2 = _read_bounded_file(temp_path)

                response.close()
                response = None
                temp_path.unlink(missing_ok=True)
                temp_path = None

                classic_url = _google_drive_classic_url(
                    original_url,
                    html_bytes_2,
                )

                if classic_url:
                    response, final_url = _safe_get(
                        session,
                        classic_url,
                        headers,
                    )
                    temp_path, first_bytes, _ = _stream_response_to_file(response)

        # ---------------------------------------------------------
        # FINAL FILE TYPE CHECK
        # ---------------------------------------------------------
        extension = _detect_extension(
            first_bytes,
            response,
            final_url,
        )

        filename = _filename_from_response(
            response,
            final_url,
            extension,
        )

        response.close()
        response = None

        # Rename temporary file to the detected extension.
        final_path = temp_path.with_suffix(extension)
        temp_path.rename(final_path)
        temp_path = None

        return final_path, filename

    except LinkDownloadError:
        raise

    except requests.RequestException as error:
        raise LinkDownloadError(
            "Could not download the spreadsheet. Make sure the link is "
            "publicly accessible and the file can be downloaded without "
            "signing in."
        ) from error

    finally:
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass

        try:
            session.close()
        except Exception:
            pass
