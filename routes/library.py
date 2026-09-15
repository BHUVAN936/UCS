from flask import Blueprint, render_template


library_bp = Blueprint(
    "library",
    __name__,
    url_prefix="/library"
)


@library_bp.route("/")
def library():
    subtopics = {
        "library_usage_teachers":
            "Per Day Usage of Library by Teachers",

        "library_usage_students":
            "Per Day Usage of Library by Students",
    }

    return render_template(
        "library/index.html",
        subtopics=subtopics
    )