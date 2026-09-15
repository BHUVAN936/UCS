"""
UCE Connect - Report Service
============================

Centralized report generation for:

    - Overall university reports
    - Module reports
    - Category reports
    - Automatic numeric analysis

This service uses the existing data_service.py.
Uploaded columns are never hard-coded.
"""

from datetime import datetime

from services.data_service import (
    MODULES,
    get_module_data,
    get_uploads,
)


# ============================================================
# HELPERS
# ============================================================

def _safe_number(value):
    """Convert a value to float when possible."""

    try:
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        text = str(value).strip()

        if not text:
            return None

        return float(text)

    except (ValueError, TypeError):
        return None


def _is_meaningful_numeric(field):
    """
    Prevent IDs and similar fields from being displayed
    as meaningful averages.
    """

    name = str(field).strip().lower()

    blocked = {
        "id",
        "student_id",
        "studentid",
        "faculty_id",
        "facultyid",
        "course_id",
        "courseid",
        "record_id",
        "recordid",
        "upload_id",
        "uploadid",
        "roll_no",
        "rollno",
        "serial_no",
        "serialno",
    }

    if name in blocked:
        return False

    if name.endswith("_id"):
        return False

    if name.endswith("id"):
        return False

    return True


def _collect_columns(rows):
    """Collect every column appearing in uploaded records."""

    columns = []
    seen = set()

    for row in rows:

        if not isinstance(row, dict):
            continue

        for column in row.keys():

            column = str(column)

            if column in seen:
                continue

            seen.add(column)
            columns.append(column)

    return columns


def _flatten_rows(grouped_data):
    """
    Convert grouped category data into a simple row list.
    """

    result = []

    if not isinstance(grouped_data, dict):
        return result

    for category_key, items in grouped_data.items():

        if not isinstance(items, list):
            continue

        for item in items:

            if not isinstance(item, dict):
                continue

            data = item.get("data", {})

            if not isinstance(data, dict):
                data = {
                    "Value": str(data)
                }

            result.append(
                {
                    "category": category_key,
                    "data": dict(data),
                    "created_at": item.get("created_at"),
                    "id": item.get("id"),
                }
            )

    return result


def _numeric_averages(rows, columns):
    """Calculate useful numeric averages."""

    averages = {}

    for column in columns:

        if not _is_meaningful_numeric(column):
            continue

        values = []

        for row in rows:

            number = _safe_number(
                row.get(column)
            )

            if number is not None:
                values.append(number)

        if values:

            averages[column] = round(
                sum(values) / len(values),
                2
            )

    return averages


# ============================================================
# CATEGORY REPORT
# ============================================================

def build_category_report(
    module_key,
    category_key
):
    """
    Build the report for one module category.
    """

    if module_key not in MODULES:

        return {
            "module_key": module_key,
            "module_name": module_key,
            "category_key": category_key,
            "category_name": category_key,
            "total_records": 0,
            "total_columns": 0,
            "columns": [],
            "rows": [],
            "latest_upload": None,
            "numeric_averages": {},
        }

    module_info = MODULES[module_key]

    categories = module_info.get(
        "categories",
        {}
    )

    category_name = categories.get(
        category_key,
        category_key
    )

    grouped_data = get_module_data(
        module_key
    )

    if not isinstance(grouped_data, dict):
        grouped_data = {}

    items = grouped_data.get(
        category_key,
        []
    )

    rows = []

    for item in items:

        if not isinstance(item, dict):
            continue

        data = item.get(
            "data",
            {}
        )

        if not isinstance(data, dict):

            data = {
                "Value": str(data)
            }

        rows.append(
            dict(data)
        )

    columns = _collect_columns(
        rows
    )

    numeric_averages = _numeric_averages(
        rows,
        columns
    )

    latest_upload = None

    if items:

        latest_upload = items[0].get(
            "created_at"
        )

    return {
        "module_key": module_key,
        "module_name": module_info.get(
            "name",
            module_key
        ),
        "category_key": category_key,
        "category_name": category_name,
        "total_records": len(rows),
        "total_columns": len(columns),
        "columns": columns,
        "rows": rows,
        "latest_upload": latest_upload,
        "numeric_averages": numeric_averages,
    }


# ============================================================
# MODULE REPORT
# ============================================================

def build_module_report(
    module_key,
    grouped_data=None
):
    """
    Build the complete report for one module.
    """

    if module_key not in MODULES:

        return {
            "module_key": module_key,
            "module_name": module_key,
            "total_records": 0,
            "total_columns": 0,
            "columns": [],
            "categories": {},
            "numeric_averages": {},
            "rows": [],
        }

    if grouped_data is None:

        grouped_data = get_module_data(
            module_key
        )

    if not isinstance(grouped_data, dict):
        grouped_data = {}

    flat = _flatten_rows(
        grouped_data
    )

    all_rows = [
        item["data"]
        for item in flat
    ]

    columns = _collect_columns(
        all_rows
    )

    category_reports = {}

    module_categories = MODULES[
        module_key
    ].get(
        "categories",
        {}
    )

    for category_key, category_name in module_categories.items():

        items = grouped_data.get(
            category_key,
            []
        )

        category_rows = []

        for item in items:

            if not isinstance(item, dict):
                continue

            data = item.get(
                "data",
                {}
            )

            if not isinstance(data, dict):

                data = {
                    "Value": str(data)
                }

            category_rows.append(
                dict(data)
            )

        category_reports[
            category_key
        ] = {
            "key": category_key,
            "name": category_name,
            "count": len(category_rows),
            "columns": _collect_columns(
                category_rows
            ),
            "rows": category_rows,
        }

    numeric_averages = _numeric_averages(
        all_rows,
        columns
    )

    return {
        "module_key": module_key,

        "module_name": MODULES[
            module_key
        ].get(
            "name",
            module_key
        ),

        "total_records": len(
            all_rows
        ),

        "total_columns": len(
            columns
        ),

        "columns": columns,

        "categories": category_reports,

        "numeric_averages":
            numeric_averages,

        "rows": all_rows,
    }


# ============================================================
# OVERALL UNIVERSITY REPORT
# ============================================================

def build_university_report():
    """
    Build the complete university report.
    """

    uploads = get_uploads()

    modules_report = []

    total_records = 0
    populated_modules = 0
    populated_categories = 0
    total_categories = 0

    for module_key, module_info in MODULES.items():

        grouped_data = get_module_data(
            module_key
        )

        module_report = build_module_report(
            module_key,
            grouped_data
        )

        category_rows = []

        categories = module_info.get(
            "categories",
            {}
        )

        total_categories += len(
            categories
        )

        for category_key, category_name in categories.items():

            count = len(
                grouped_data.get(
                    category_key,
                    []
                )
            )

            if count > 0:
                populated_categories += 1

            category_rows.append(
                {
                    "key": category_key,
                    "name": category_name,
                    "count": count,
                }
            )

        if module_report[
            "total_records"
        ] > 0:

            populated_modules += 1

        total_records += module_report[
            "total_records"
        ]

        numeric_values = []

        for field, value in module_report[
            "numeric_averages"
        ].items():

            numeric_values.append(
                {
                    "field": field,
                    "value": value,
                }
            )

        modules_report.append(
            {
                "key": module_key,

                "name": module_info.get(
                    "name",
                    module_key
                ),

                "description": module_info.get(
                    "description",
                    ""
                ),

                "icon": module_info.get(
                    "icon",
                    "fa-folder"
                ),

                "total_records":
                    module_report[
                        "total_records"
                    ],

                "total_columns":
                    module_report[
                        "total_columns"
                    ],

                "categories":
                    category_rows,

                "numeric_averages":
                    numeric_values[:8],
            }
        )

    return {
        "generated_at":
            datetime.now().strftime(
                "%d %b %Y, %I:%M %p"
            ),

        "total_records":
            total_records,

        "total_uploads":
            len(uploads),

        "populated_modules":
            populated_modules,

        "total_modules":
            len(MODULES),

        "populated_categories":
            populated_categories,

        "total_categories":
            total_categories,

        "modules":
            modules_report,

        "recent_uploads":
            uploads[:8],
    }


# ============================================================
# COMPATIBILITY FUNCTIONS
# ============================================================

def get_module_report(module_key):

    return build_module_report(
        module_key
    )


def get_overall_report():

    return build_university_report()


def build_overall_report():

    return build_university_report()