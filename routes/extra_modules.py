from flask import Blueprint, render_template

from services.data_service import (
    MODULES,
    build_module_report,
    get_module_data,
    prepare_module_tables,
)


extra_modules_bp = Blueprint(
    "extra_modules",
    __name__,
)


def _render_module(module_key):
    module_info = MODULES[module_key]
    grouped_data = get_module_data(module_key)
    report = build_module_report(module_key, grouped_data)
    tables = prepare_module_tables(grouped_data)

    return render_template(
        "module_report/index.html",
        module_key=module_key,
        module_info=module_info,
        subtopics=module_info.get("categories", {}),
        grouped_data=grouped_data,
        report=report,
        tables=tables,
    )


@extra_modules_bp.route("/alumni")
def alumni():
    return _render_module("alumni")


@extra_modules_bp.route("/finance")
def finance():
    return _render_module("finance")
