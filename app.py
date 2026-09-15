from flask import Flask

from config import Config
from database.db import init_database

from routes.main import main_bp

from routes.academics import academics_bp
from routes.placements import placements_bp
from routes.counselling import counselling_bp
from routes.exams_evaluation import exams_evaluation_bp
from routes.progression import progression_bp
from routes.faculty_fdp_inhouse import faculty_fdp_inhouse_bp
from routes.workload_of_students import workload_of_students_bp
from routes.moocs import moocs_bp
from routes.mous_international import mous_international_bp
from routes.student_abroad_program import student_abroad_program_bp
from routes.faculty_exchange_abroad import faculty_exchange_abroad_bp
from routes.faculty_affairs import faculty_affairs_bp
from routes.visiting_faculty import visiting_faculty_bp
from routes.research import research_bp
from routes.faculty_fdp_corporate import faculty_fdp_corporate_bp
from routes.student_entrepreneurship import student_entrepreneurship_bp
from routes.sac import sac_bp
from routes.p_and_d import p_and_d_bp
from routes.registrar_office import registrar_office_bp
from routes.library import library_bp


def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    init_database()

    app.register_blueprint(main_bp)

    app.register_blueprint(academics_bp)
    app.register_blueprint(placements_bp)
    app.register_blueprint(counselling_bp)
    app.register_blueprint(exams_evaluation_bp)
    app.register_blueprint(progression_bp)
    app.register_blueprint(faculty_fdp_inhouse_bp)
    app.register_blueprint(workload_of_students_bp)
    app.register_blueprint(moocs_bp)
    app.register_blueprint(mous_international_bp)
    app.register_blueprint(student_abroad_program_bp)
    app.register_blueprint(faculty_exchange_abroad_bp)
    app.register_blueprint(faculty_affairs_bp)
    app.register_blueprint(visiting_faculty_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(faculty_fdp_corporate_bp)
    app.register_blueprint(student_entrepreneurship_bp)
    app.register_blueprint(sac_bp)
    app.register_blueprint(p_and_d_bp)
    app.register_blueprint(registrar_office_bp)
    app.register_blueprint(library_bp)

    return app


app = create_app()


if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )