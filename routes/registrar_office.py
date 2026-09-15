from flask import Blueprint, render_template

from services.data_service import (
    MODULES,
    build_module_report,
    get_module_data,
    prepare_module_tables,
)


registrar_office_bp = Blueprint(
    "registrar_office",
    __name__,
    url_prefix="/registrar-office"
)


@registrar_office_bp.route("/")
def index():

    module_key = "registrar_office"

    grouped_data = get_module_data(module_key)

    report = build_module_report(
        module_key,
        grouped_data
    )

    tables = prepare_module_tables(
        grouped_data
    )

    return render_template(
        "registrar_office/index.html",
        module_key=module_key,
        module_info=MODULES[module_key],
        subtopics=MODULES[module_key]["categories"],
        grouped_data=grouped_data,
        report=report,
        tables=tables,
    )