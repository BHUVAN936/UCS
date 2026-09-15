from flask import Blueprint, render_template

from services.data_service import (
    MODULES,
    build_module_report,
    get_module_data,
    prepare_module_tables,
)


sac_bp = Blueprint(
    "sac",
    __name__,
    url_prefix="/sac"
)


@sac_bp.route("/")
def index():

    module_key = "sac"

    grouped_data = get_module_data(module_key)

    report = build_module_report(
        module_key,
        grouped_data
    )

    tables = prepare_module_tables(
        grouped_data
    )

    return render_template(
        "sac/index.html",
        module_key=module_key,
        module_info=MODULES[module_key],
        subtopics=MODULES[module_key]["categories"],
        grouped_data=grouped_data,
        report=report,
        tables=tables,
    )