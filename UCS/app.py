from flask import Flask

from config import Config
from database.db import init_database

from routes.main import main_bp
from routes.academics import academics_bp
from routes.faculty_fdp_inhouse import faculty_bp
from routes.students import students_bp
from routes.research import research_bp
from routes.skills import skills_bp
from routes.projects import projects_bp
from routes.training import training_bp
from routes.placements import placements_bp
from routes.practice_school import practice_school_bp


def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    # Initialize database
    init_database()

    # Register application routes
    app.register_blueprint(main_bp)
    app.register_blueprint(academics_bp)
    app.register_blueprint(faculty_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(skills_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(placements_bp)
    app.register_blueprint(practice_school_bp)

    return app


app = create_app()


if __name__ == "__main__":

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )