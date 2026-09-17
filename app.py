from flask import Flask

from config import Config
from database.db import init_database

# =========================================================
# MAIN ROUTE
# =========================================================

from routes.main import main_bp


# =========================================================
# 01 - 20 MODULE ROUTES
# =========================================================

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


# =========================================================
# APPLICATION FACTORY
# =========================================================

def create_app():

    app = Flask(__name__)

    # -----------------------------------------------------
    # Load configuration
    # -----------------------------------------------------

    app.config.from_object(Config)

    # -----------------------------------------------------
    # Initialize database
    # -----------------------------------------------------

    init_database()

    # -----------------------------------------------------
    # Register main blueprint
    # -----------------------------------------------------

    app.register_blueprint(main_bp)

    # -----------------------------------------------------
    # 01 Academics
    # -----------------------------------------------------

    app.register_blueprint(academics_bp)

    # -----------------------------------------------------
    # 02 Placements
    # -----------------------------------------------------

    app.register_blueprint(placements_bp)

    # -----------------------------------------------------
    # 03 Counselling
    # -----------------------------------------------------

    app.register_blueprint(counselling_bp)

    # -----------------------------------------------------
    # 04 Exams & Evaluation
    # -----------------------------------------------------

    app.register_blueprint(exams_evaluation_bp)

    # -----------------------------------------------------
    # 05 Progression
    # -----------------------------------------------------

    app.register_blueprint(progression_bp)

    # -----------------------------------------------------
    # 06 Faculty FDP In-House
    # -----------------------------------------------------

    app.register_blueprint(faculty_fdp_inhouse_bp)

    # -----------------------------------------------------
    # 07 Workload of Students
    # -----------------------------------------------------

    app.register_blueprint(workload_of_students_bp)

    # -----------------------------------------------------
    # 08 MOOCs
    # -----------------------------------------------------

    app.register_blueprint(moocs_bp)

    # -----------------------------------------------------
    # 09 MOUs - International
    # -----------------------------------------------------

    app.register_blueprint(mous_international_bp)

    # -----------------------------------------------------
    # 10 Student Abroad Program
    # -----------------------------------------------------

    app.register_blueprint(student_abroad_program_bp)

    # -----------------------------------------------------
    # 11 Faculty Exchange Abroad
    # -----------------------------------------------------

    app.register_blueprint(faculty_exchange_abroad_bp)

    # -----------------------------------------------------
    # 12 Faculty Affairs
    # -----------------------------------------------------

    app.register_blueprint(faculty_affairs_bp)

    # -----------------------------------------------------
    # 13 Visiting Faculty
    # -----------------------------------------------------

    app.register_blueprint(visiting_faculty_bp)

    # -----------------------------------------------------
    # 14 Research
    # -----------------------------------------------------

    app.register_blueprint(research_bp)

    # -----------------------------------------------------
    # 15 Faculty FDP Corporate
    # -----------------------------------------------------

    app.register_blueprint(faculty_fdp_corporate_bp)

    # -----------------------------------------------------
    # 16 Student Entrepreneurship
    # -----------------------------------------------------

    app.register_blueprint(student_entrepreneurship_bp)

    # -----------------------------------------------------
    # 17 SAC
    # -----------------------------------------------------

    app.register_blueprint(sac_bp)

    # -----------------------------------------------------
    # 18 P&D
    # -----------------------------------------------------

    app.register_blueprint(p_and_d_bp)

    # -----------------------------------------------------
    # 19 Registrar Office
    # -----------------------------------------------------

    app.register_blueprint(registrar_office_bp)

    # -----------------------------------------------------
    # 20 Library
    # -----------------------------------------------------

    app.register_blueprint(library_bp)

    return app


# =========================================================
# CREATE APPLICATION
# =========================================================

app = create_app()


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )