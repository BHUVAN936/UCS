from flask import Blueprint, render_template

from services.data_service import (
    MODULES,
    build_module_report,
    get_module_data,
    prepare_module_tables,
)


student_entrepreneurship_bp = Blueprint(
    "student_entrepreneurship",
    __name__,
    url_prefix="/student-entrepreneurship"
)


@student_entrepreneurship_bp.route("/")
def index():

    module_key = "student_entrepreneurship"

    grouped_data = get_module_data(module_key)

    report = build_module_report(
        module_key,
        grouped_data
    )

    tables = prepare_module_tables(
        grouped_data
    )

    return render_template(
        "student_entrepreneurship/index.html",
        module_key=module_key,
        module_info=MODULES[module_key],
        subtopics=MODULES[module_key]["categories"],
        grouped_data=grouped_data,
        report=report,
        tables=tables,
    )