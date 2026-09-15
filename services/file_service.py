import json
from pathlib import Path

import pandas as pd
from pypdf import PdfReader


def clean_value(value):

    if pd.isna(value):

        return ""

    if hasattr(value, "item"):

        try:

            value = value.item()

        except (
            ValueError,
            TypeError
        ):

            pass

    if isinstance(
        value,
        float
    ):

        if value.is_integer():

            return int(value)

    return value


def clean_records(records):

    cleaned = []

    for record in records:

        cleaned.append(
            {
                str(key): clean_value(value)
                for key, value
                in record.items()
            }
        )

    return cleaned


def extract_csv(file_path):

    dataframe = pd.read_csv(
        file_path
    )

    dataframe = dataframe.fillna("")

    records = dataframe.to_dict(
        orient="records"
    )

    return clean_records(
        records
    )


def extract_excel(file_path):

    dataframe = pd.read_excel(
        file_path
    )

    dataframe = dataframe.fillna("")

    records = dataframe.to_dict(
        orient="records"
    )

    return clean_records(
        records
    )


def extract_pdf(file_path):

    reader = PdfReader(
        file_path
    )

    pages = []

    for page_number, page in enumerate(
        reader.pages,
        start=1
    ):

        text = (
            page.extract_text()
            or ""
        )

        if text.strip():

            pages.append(
                {
                    "page": page_number,
                    "content": text.strip()
                }
            )

    return pages


def extract_file(file_path):

    extension = (
        Path(file_path)
        .suffix
        .lower()
    )

    if extension == ".csv":

        return (
            extract_csv(file_path),
            "csv"
        )

    if extension in {
        ".xlsx",
        ".xls"
    }:

        return (
            extract_excel(file_path),
            extension.replace(
                ".",
                ""
            )
        )

    if extension == ".pdf":

        return (
            extract_pdf(file_path),
            "pdf"
        )

    raise ValueError(
        "Unsupported file type."
    )


def prepare_json(data):

    return json.dumps(
        data,
        ensure_ascii=False,
        default=str
    )