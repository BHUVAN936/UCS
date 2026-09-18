import io
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from database.db import get_connection
from services.link_service import download_spreadsheet


# =========================================================
# 20 MODULES
# =========================================================

MODULES = {
    "academics": {
        "name": "Academics",
        "icon": "fa-book-open",
        "description": "Academic programmes, curriculum and attainment.",
        "categories": {
            "syllabus_revision": "Syllabus revision – No of Programmes",
            "new_courses_introduced": "New Courses introduced",
            "value_added_courses": "Number of value-added courses",
            "co_attainment_all_courses": "CO Attainment-All Courses",
            "po_attainment_all_programs": "PO Attainment-All Programs",
        },
    },

    "placements": {
        "name": "Placements",
        "icon": "fa-briefcase",
        "description": "Internships, placements, higher education and competitive examinations.",
        "categories": {
            "internships_projects_practice_school": "Students undertaking internships/projects/practice school",
            "students_to_be_placed": "Number of students to be placed",
            "students_to_go_higher_education": "Number of students to go for higher education",
            "students_to_appear_competitive_exams": "Number of students to appear for Competitive Exams",
            "students_qualified_competitive_exams": "Number of students to be qualified in Competitive Exams",
            "students_qualified_placed_international": "Number of students qualified & placed in international placements",
        },
    },

    "counselling": {
        "name": "Counselling",
        "icon": "fa-comments",
        "description": "Student counselling and mentoring.",
        "categories": {
            "number_of_counsellors": "Number of counsellors (with 1:20 ratio on campus student strength)",
            "girl_students_mentoring": "% Girl students benefited from university through mentoring",
        },
    },

    "exams_evaluation": {
        "name": "Exams & Evaluation",
        "icon": "fa-file-circle-check",
        "description": "Examination and result declaration.",
        "categories": {
            "result_declaration_days": "No. of days to declare the results including the in-semester exams",
        },
    },

    "progression": {
        "name": "Progression",
        "icon": "fa-arrow-trend-up",
        "description": "Student graduation.",
        "categories": {
            "students_graduated_final_year": "Number of students to be Graduated (Final Year)",
        },
    },

    "faculty_fdp_inhouse": {
        "name": "Faculty FDP In-House",
        "icon": "fa-chalkboard-user",
        "description": "Faculty and non-teaching staff professional development and training.",
        "categories": {
            "professional_development_admin_training": "Number of professional development/ administrative training programmes organized for faculty/non-teaching staff (Academic Staff College)",
            "teachers_fdp": "No of Teachers undergoing online/face-to-face faculty Development programmes (FDP)",
        },
    },

    "workload_of_students": {
        "name": "Workload of Students",
        "icon": "fa-clock",
        "description": "Student contact hours.",
        "categories": {
            "contact_hours_per_week": "Contact hours per week",
        },
    },

    "moocs": {
        "name": "MOOCs",
        "icon": "fa-laptop",
        "description": "Self-study hours in the timetable.",
        "categories": {
            "self_study_hours_timetable": "Self-study hours in Timetable",
        },
    },

    "mous_international": {
        "name": "MOUs-International",
        "icon": "fa-handshake",
        "description": "International academic collaborations.",
        "categories": {
            "active_mous_academics": "International collaborations: Number of Active MOUs (Related to Academics)",
        },
    },

    "student_abroad_program": {
        "name": "Student Abroad Program",
        "icon": "fa-earth-americas",
        "description": "International student mobility and overseas programmes.",
        "categories": {
            "summer_winter_overseas_internship": "International collaborations: Number of students going for Summer/Winter school (overseas internship)",
            "dual_degrees_international": "International collaborations: Number of students doing Dual Degrees (International)",
            "semester_exchange_student_inbound": "International collaborations: Number of Semester Exchange (Student) Inbound",
            "semester_exchange_student_outbound": "International collaborations: Number of Semester Exchange (Student) outbound",
            "student_exchange_inbound_2_weeks": "Number of Student Exchange Inbound for 2 weeks",
            "student_exchange_outbound_2_weeks": "Number of Student Exchange Outbound for 2 weeks",
        },
    },

    "faculty_exchange_abroad": {
        "name": "Faculty Exchange Abroad",
        "icon": "fa-plane",
        "description": "International faculty exchange.",
        "categories": {
            "semester_exchange_faculty_inbound": "International collaborations: Number of Semester Exchange (Faculty) Inbound",
            "semester_exchange_faculty_outbound": "International collaborations: Number of Semester Exchange (Faculty) outbound",
            "faculty_inbound_2_weeks": "Number of Faculty Inbound for 2 weeks",
            "faculty_outbound_2_weeks": "Number of Faculty Outbound for 2 weeks",
        },
    },

    "faculty_affairs": {
        "name": "Faculty Affairs",
        "icon": "fa-user-tie",
        "description": "Faculty strength, qualifications, experience, support and entrepreneurship.",
        "categories": {
            "full_time_teachers_sanctioned_posts": "Number of full-time teachers against sanctioned posts (1:15 Ratio)",
            "women_faculty": "Women faculty",
            "foreign_faculty": "Foreign faculty",
            "full_time_teachers_phd": "Full time teachers with Ph. D",
            "faculty_experience": "Faculty experience",
            "faculty_external_nonacademic_experience": "Faculty with at least two years part-time or full-time experience in external nonacademic organisation",
            "teachers_financial_support": "Number of Teachers provided with financial support to attend conferences / workshops and towards membership fee of professional bodies",
            "retention_ratio": "Retention ratio (Tenure: 3 + years)",
            "external_consultations": "External consultations -faculty with a parallel appointment in a non-academic position (Industry, NGO, government committee, etc.)",
            "faculty_entrepreneurship_experience": "Faculty with entrepreneurship experience -Proportion of faculty with experience of working in or running their own/co-founded start-up",
            "demand_ratio": "Demand Ratio",
        },
    },

    "visiting_faculty": {
        "name": "Visiting faculty",
        "icon": "fa-user-group",
        "description": "Visiting industry and academic experts.",
        "categories": {
            "visiting_faculty_industry_academic": "Number of Visiting Faculty (Industry/Academic Experts)",
        },
    },

    "research": {
        "name": "Research",
        "icon": "fa-flask",
        "description": "Research funding, publications, patents, scholars, centres and collaborations.",
        "categories": {
            "seed_money": "Seed money",
            "research_fellows_enrolled": "Number of JRFs, SRFs, Post-Doctoral Fellows, Research Associates and other research fellows enrolled",
            "sponsored_research_projects_govt": "Sponsored Research Projects amount (GOVT)",
            "sponsored_research_projects_non_govt": "Sponsored Research Projects amount (NON GOVT)",
            "consultancy_royalty_revenue": "Revenue generated from consultancy + Royalty",
            "executive_development_programs": "Executive development programs with min 10 months duration (Academic Staff College) with min 20 intake per Department and revenue of 1.8 crs",
            "research_funding_proposals_submitted": "Number of research funding proposals submitted",
            "research_funding_proposals_approved_active": "Number of research funding proposals approved and active",
            "fellowships_national_international": "Number of fellowships (national/international)",
            "ipr_workshops_seminars": "Number of workshops/seminars conducted on IPR",
            "research_awards_recognitions": "Number of awards / recognitions received for research/ innovations by the institution/teachers/research scholars/ students",
            "patents_published": "Number of Patents published. (Utility patent – Published)",
            "patents_granted": "Number of Patents- Granted",
            "ip_commercialisation": "Commercialisation of Intellectual Property",
            "h_index_scopus": "H index-Scopus",
            "h_index_wos": "H index -WoS",
            "phds_awarded": "Number of Ph.Ds awarded",
            "research_papers_published": "Number of Research papers published",
            "books_chapters_published": "Number of books and chapters in edited volumes published",
            "conference_papers_published": "Number of conference papers published",
            "citations": "Number of Citations",
            "full_time_phd_scholars": "Full time Ph.D. scholars",
            "active_research_centres": "Number of active Research Centres with atlest One ongoing govt funded project and Publications",
            "international_conferences_research_reports": "International conferences organised, and research reports published by the Research centre in the last 12 months",
            "joint_research_international": "Number of Joint Research (International collaborations) activities (other than paper and book publications)-1 per dept/year",
            "joint_conferences_international": "Number of Joint Conferences with International collaborations",
        },
    },

    "faculty_fdp_corporate": {
        "name": "Faculty FDP Corporate",
        "icon": "fa-building",
        "description": "Corporate training programmes and revenue.",
        "categories": {
            "corporate_training_programs": "No.of corporate training Programs per year",
            "corporate_training_revenue": "Revenue generated from corporate training",
        },
    },

    "student_entrepreneurship": {
        "name": "Student Entreprenuership",
        "icon": "fa-lightbulb",
        "description": "Student entrepreneurship training and start-ups.",
        "categories": {
            "entrepreneurship_training_25_hours": "Number of students who completed at least 25 hours entrepreneurship training course on/offcampus",
            "students_willing_business": "Students with entrepreneurship: Number of students willing to start own business",
            "startups_incubated": "No. of start-ups incubated on campus",
        },
    },

    "sac": {
        "name": "SAC",
        "icon": "fa-people-group",
        "description": "Extension, clubs, student participation, gender equity and professional ethics activities.",
        "categories": {
            "extension_outreach_programs": "Number of extension and outreach programs to be conducted through NSS/NCC/Red Cross/YRC",
            "students_extension_activities": "Number of Students participating in extension activities",
            "sports_cultural_awards": "Number of awards/medals won by students for outstanding performance in sports/cultural activities at inter-university/state/ national/international events",
            "clubs_technical_societies": "Clubs’ activities or Technical societies and their Concerts & Exhibitions",
            "students_clubs_societies_associations": "Number of students involved in Clubs/Student societies /Associations on campus",
            "gender_equity_activities": "Number of Activities planned on Gender equity",
            "professional_ethics_events": "Number of events/workshops conducted by the college to develop students’ professional ethics",
        },
    },

    "p_and_d": {
        "name": "P&D",
        "icon": "fa-chart-line",
        "description": "Planning, development and infrastructure facilities.",
        "categories": {
            "extension_activity_awards": "Number of awards received by institution, teachers and students from Gov./Gov. recognized bodies in extension activities",
            "classrooms_tutorial_rooms": "Total number of classrooms including Tutorial rooms",
            "labs": "Total number of Labs",
            "ict_enabled_classrooms": "Number of classrooms with ICT-enabled facilities",
            "student_computers": "Total number of computers (For students only 1:4)",
            "office_faculty_computers": "Number of computers for office work/faculty",
        },
    },

    "registrar_office": {
        "name": "Registrar Office",
        "icon": "fa-building-columns",
        "description": "Student admissions, scholarships, reservations and enrolment information.",
        "categories": {
            "scholarships_freeships": "Number of students benefited by scholarships and Freeships provided by the institution, Government, and NGOs",
            "full_tuition_fee_reimbursement": "Full Tuition Fee reimbursement for economically and socially challenged students",
            "girl_students_scholarships": "% Girl students benefited from university through scholarships",
            "career_counselling_competitive_exams": "Number of students benefited by career counselling and guidance for competitive examinations",
            "total_seats_filled": "Total number of seats filled against sanctioned seats",
            "reserved_category_seats": "Seats filled against reserved categories (SC, ST, OBC, Divyangjan, etc.)",
            "girl_students_enrolled": "Percentage of girl students enrolled",
            "students_other_states": "Percentage of students enrolled from other states",
            "students_other_countries": "Percentage of students enrolled from other countries",
            "first_generation_students": "Number of first-generation students admitted in 1st year",
            "first_generation_girl_students": "Number of first-generation Girl Students admitted in 1st year",
        },
    },

    "alumni": {
        "name": "Alumni",
        "icon": "fa-user-graduate",
        "description": "Alumni contribution and entrepreneurship.",
        "categories": {
            "alumni_contribution": "Alumni contribution",
            "alumni_entrepreneurship": "Alumni with entrepreneurship: Number of alumni running their own/co-founded start-up within 5 years after graduation",
        },
    },

    "finance": {
        "name": "Finance",
        "icon": "fa-coins",
        "description": "Salary and infrastructure development funding.",
        "categories": {
            "median_salary_ug": "Median salary – UG",
            "median_salary_pg": "Median salary – PG",
            "government_infrastructure_grants": "Funds / Grants received from government bodies for development and maintenance of infrastructure (not covered under criteria III and V) (INR in Lakhs)",
            "non_government_infrastructure_grants": "Funds / Grants received from non-government bodies, individuals, philanthropists for development and maintenance of infrastructure (not covered under criteria III and V) (INR in Rs. Lakhs)",
        },
    },

    "library": {
        "name": "Library",
        "icon": "fa-book",
        "description": "Daily library usage by teachers and students.",
        "categories": {
            "library_usage_teachers": "Per day usage of library by teachers",
            "library_usage_students": "Per day usage of library by students",
        },
    },
}


# =========================================================
# ALIASES
# =========================================================

MODULE_ALIASES = {
    "faculty_exchange": "faculty_exchange_abroad",
    "placementa": "placements",
    "faculty_fdp_corporate": "faculty_fdp_corporate",
    "faculty_fdp_in_house": "faculty_fdp_inhouse",
    "faculty_fdp_inhouse": "faculty_fdp_inhouse",
    "exams": "exams_evaluation",
    "exam_evaluation": "exams_evaluation",
    "p&d": "p_and_d",
    "planning_and_development": "p_and_d",
}


# =========================================================
# STRONG MODULE KEYWORDS
# =========================================================

MODULE_KEYWORDS = {
    "faculty_fdp_corporate": [
        "faculty fdp corporate",
        "corporate fdp",
        "corporate training",
        "corporate faculty development",
    ],

    "faculty_fdp_inhouse": [
        "faculty fdp inhouse",
        "faculty fdp in-house",
        "inhouse fdp",
        "in-house fdp",
        "in house fdp",
    ],

    "faculty_exchange_abroad": [
        "faculty exchange abroad",
        "faculty exchange",
        "faculty abroad",
    ],

    "student_abroad_program": [
        "student abroad program",
        "student abroad",
        "study abroad",
        "student exchange",
    ],

    "student_entrepreneurship": [
        "student entrepreneurship",
        "entrepreneurship",
        "entrepreneur",
        "startup",
        "startups",
    ],

    "mous_international": [
        "mou international",
        "international mou",
        "international mous",
        "memorandum of understanding",
    ],

    "visiting_faculty": [
        "visiting faculty",
        "guest faculty",
    ],

    "workload_of_students": [
        "workload of students",
        "student workload",
    ],

    "exams_evaluation": [
        "exams evaluation",
        "exam evaluation",
        "examination",
        "exams",
        "result declaration",
    ],

    "registrar_office": [
        "registrar office",
        "registrar",
    ],

    "research": [
        "research",
        "research project",
        "publication",
        "publications",
        "patent",
        "research paper",
    ],

    "library": [
        "library",
        "library usage",
        "library books",
        "library journals",
        "e-resources",
        "e resources",
    ],

    "counselling": [
        "counselling",
        "counseling",
        "counsellor",
        "counselor",
        "mentoring",
    ],

    "placements": [
        "placement",
        "placements",
        "internship",
        "internships",
        "practice school",
        "higher education",
        "competitive exam",
        "international placement",
    ],

    "progression": [
        "progression",
        "graduated",
        "graduation",
    ],

    "moocs": [
        "mooc",
        "moocs",
    ],

    "sac": [
        "sac",
        "student activity",
        "student activities",
        "club",
        "clubs",
        "student event",
    ],

    "p_and_d": [
        "p&d",
        "planning and development",
        "planning",
    ],

    "faculty_affairs": [
        "faculty affairs",
        "faculty information",
    ],

    "academics": [
        "academics",
        "academic",
        "syllabus",
        "curriculum",
        "co attainment",
        "po attainment",
        "value-added course",
        "new courses introduced",
    ],
}


# =========================================================
# CATEGORY ALIASES
# =========================================================

# Maps user/form/header variants back to the exact configured category key.
# This prevents values such as "syllabus revision" from being stored as a
# different key from "syllabus_revision".
CATEGORY_ALIASES = {}

for _module_key, _module_info in MODULES.items():
    CATEGORY_ALIASES.setdefault(_module_key, {})
    for _category_key, _category_label in _module_info.get("categories", {}).items():
        _variants = {
            _category_key,
            _category_label,
            _category_key.replace("_", " "),
            _category_label.replace("–", "-"),
            _category_label.replace("—", "-"),
        }
        for _variant in _variants:
            CATEGORY_ALIASES[_module_key][re.sub(r"\s+", " ", str(_variant).strip().lower().replace("&", " and ").replace("_", " ").replace("-", " ")).strip()] = _category_key

# A global alias map is also kept for routes that only have a category.
GLOBAL_CATEGORY_ALIASES = {}
for _module_aliases in CATEGORY_ALIASES.values():
    for _alias, _key in _module_aliases.items():
        GLOBAL_CATEGORY_ALIASES.setdefault(_alias, _key)


# =========================================================
# NORMALIZATION
# =========================================================

def normalize_text(value):
    if value is None:
        return ""

    text = str(value).strip().lower()

    text = text.replace("&", " and ")
    text = text.replace("_", " ")
    text = text.replace("-", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_module(module):
    text = normalize_text(module)

    return MODULE_ALIASES.get(
        text,
        text.replace(" ", "_")
    )


def normalize_category(category, module=None):
    """Return the exact configured category key for a user/header variant."""
    if category is None:
        return ""

    target = normalize_text(category)
    if not target:
        return ""

    if module:
        module_key = normalize_module(module)
        aliases = CATEGORY_ALIASES.get(module_key, {})
        if target in aliases:
            return aliases[target]

        # Also try the exact configured key after underscore normalization.
        for key in MODULES.get(module_key, {}).get("categories", {}):
            if normalize_text(key) == target:
                return key

    if target in GLOBAL_CATEGORY_ALIASES:
        return GLOBAL_CATEGORY_ALIASES[target]

    # Last safe fallback: only return an underscore key, never an arbitrary
    # display label.
    return target.replace(" ", "_")



# =========================================================
# ROW HELPERS
# =========================================================

def row_text(row):
    if isinstance(row, pd.Series):
        values = row.to_dict().values()
    elif isinstance(row, dict):
        values = row.values()
    else:
        return ""

    result = []

    for value in values:
        if pd.isna(value):
            continue

        result.append(str(value))

    return " ".join(result).lower()


def get_column_value(row, names):
    if isinstance(row, pd.Series):
        data = row.to_dict()
    elif isinstance(row, dict):
        data = row
    else:
        return ""

    normalized = {
        normalize_text(key): value
        for key, value in data.items()
    }

    for name in names:
        key = normalize_text(name)

        if key in normalized:
            value = normalized[key]

            if pd.notna(value):
                return str(value).strip()

    return ""


# =========================================================
# EXPLICIT MODULE / CATEGORY DETECTION
# =========================================================

def detect_explicit_module(row):
    value = get_column_value(
        row,
        [
            "module",
            "module name",
            "module_name",
            "department module",
            "category module",
        ],
    )
    if not value:
        return None

    normalized = normalize_module(value)
    if normalized in MODULES:
        return normalized

    target = normalize_text(value)
    for key, info in MODULES.items():
        if target == normalize_text(info.get("name", key)):
            return key
    return None


def detect_explicit_category(module, row):
    module = normalize_module(module)
    if module not in MODULES:
        return None

    value = get_column_value(
        row,
        [
            "sub-module", "sub module", "submodule",
            "category", "category name", "subtopic", "topic",
            "metric", "indicator", "parameter",
        ],
    )
    if not value:
        return None

    target = normalize_text(value)
    aliases = CATEGORY_ALIASES.get(module, {})
    if target in aliases:
        return aliases[target]

    for key, label in MODULES[module].get("categories", {}).items():
        if target in {normalize_text(key), normalize_text(label)}:
            return key

    return None


# =========================================================
# SHEET-LEVEL MODULE DETECTION
# =========================================================

SHEET_MODULE_ALIASES = {
    "academic performance": "academics",
    "academic performance data": "academics",
    "academics": "academics",
    "placements": "placements",
    "placement": "placements",
    "research": "research",
    "student activities": "sac",
    "student activity": "sac",
    "internships": "placements",
    "internship": "placements",
    "counselling": "counselling",
    "counseling": "counselling",
    "faculty": "faculty_affairs",
    "faculty affairs": "faculty_affairs",
    "scholarships": "registrar_office",
    "scholarship": "registrar_office",
}


# =========================================================
# PRECISE COLUMN -> SUBMODULE RULES
# =========================================================
# A mixed sheet can contain fields for several modules.  The old importer
# forced the whole row into one module/category.  These rules instead inspect
# the COLUMN NAMES and create a separate record for every clearly matched
# submodule.  Values are never used as the primary evidence for classification.
# If a row does not match a configured submodule, it stays unclassified.

CATEGORY_COLUMN_HINTS = {
    "academics": {
        "syllabus_revision": ["syllabus_revision", "syllabus_revision_programmes", "no_of_programmes_syllabus_revision"],
        "new_courses_introduced": ["new_courses_introduced", "new_courses", "courses_introduced"],
        "value_added_courses": ["value_added_courses", "number_of_value_added_courses", "value_added_course_count"],
        "co_attainment_all_courses": ["co_attainment_percentage", "co_attainment", "co_attainment_all_courses"],
        "po_attainment_all_programs": ["po_attainment_percentage", "po_attainment", "po_attainment_all_programs"],
    },
    "placements": {
        "internships_projects_practice_school": ["internship_status", "project_status", "internship", "internships", "practice_school", "practice_school_status", "project_type"],
        "students_to_be_placed": ["placement_status", "students_to_be_placed", "to_be_placed"],
        "students_to_go_higher_education": ["higher_education", "higher_education_status", "students_to_go_higher_education"],
        "students_to_appear_competitive_exams": ["competitive_exam", "competitive_exams", "students_to_appear_competitive_exams"],
        "students_qualified_competitive_exams": ["competitive_exam_status", "qualified_competitive_exam", "students_qualified_competitive_exams"],
        "students_qualified_placed_international": ["international_placement", "international_placement_status", "students_qualified_placed_international"],
    },
    "counselling": {
        "number_of_counsellors": ["counsellor_id", "counsellor", "counselor_id", "counselor", "number_of_counsellors", "counselling_id"],
        "girl_students_mentoring": ["gender_mentoring", "girl_students_mentoring", "girl_students_mentored"],
    },
    "exams_evaluation": {
        "result_declaration_days": ["result_declaration_days", "result_declaration", "days_to_declare_results", "result_days"],
    },
    "progression": {
        "students_graduated_final_year": ["students_graduated_final_year", "graduated", "graduation_status"],
    },
    "faculty_fdp_inhouse": {
        "professional_development_admin_training": ["professional_development", "administrative_training", "admin_training_programmes", "professional_development_admin_training"],
        "teachers_fdp": ["fdp_inhouse", "fdp_in_house", "teachers_fdp", "faculty_development_programme", "faculty_development_programmes"],
    },
    "workload_of_students": {
        "contact_hours_per_week": ["contact_hours_per_week", "contact_hours", "weekly_contact_hours"],
    },
    "moocs": {
        "self_study_hours_timetable": ["self_study_hours", "self_study_hours_timetable", "timetable_self_study_hours"],
    },
    "mous_international": {
        "active_mous_academics": ["active_mous", "active_mous_academics", "international_mous", "mou_count"],
    },
    "student_abroad_program": {
        "summer_winter_overseas_internship": ["summer_winter_overseas_internship", "summer_school", "winter_school", "overseas_internship"],
        "dual_degrees_international": ["dual_degree", "dual_degrees", "dual_degree_international", "dual_degrees_international"],
        "semester_exchange_student_inbound": ["student_exchange_inbound", "semester_exchange_student_inbound"],
        "semester_exchange_student_outbound": ["student_exchange_outbound", "semester_exchange_student_outbound"],
        "student_exchange_inbound_2_weeks": ["student_exchange_inbound_2_weeks"],
        "student_exchange_outbound_2_weeks": ["student_exchange_outbound_2_weeks"],
    },
    "faculty_exchange_abroad": {
        "semester_exchange_faculty_inbound": ["faculty_exchange_inbound", "semester_exchange_faculty_inbound"],
        "semester_exchange_faculty_outbound": ["faculty_exchange_outbound", "semester_exchange_faculty_outbound"],
        "faculty_inbound_2_weeks": ["faculty_inbound_2_weeks"],
        "faculty_outbound_2_weeks": ["faculty_outbound_2_weeks"],
    },
    "faculty_affairs": {
        "full_time_teachers_sanctioned_posts": ["full_time_teachers", "sanctioned_posts", "teacher_sanctioned_posts"],
        "women_faculty": ["women_faculty", "female_faculty"],
        "foreign_faculty": ["foreign_faculty"],
        "full_time_teachers_phd": ["phd_status", "ph_d_status", "full_time_teachers_phd", "teachers_with_phd"],
        "faculty_experience": ["experience_years", "faculty_experience", "experience"],
        "faculty_external_nonacademic_experience": ["industry_experience", "external_nonacademic_experience", "nonacademic_experience"],
        "teachers_financial_support": ["teachers_financial_support", "conference_support", "financial_support"],
        "retention_ratio": ["retention_status", "retention_ratio"],
        "external_consultations": ["external_consultations", "parallel_appointment", "external_consultation"],
        "faculty_entrepreneurship_experience": ["entrepreneurship_experience", "faculty_entrepreneurship_experience"],
        "demand_ratio": ["demand_ratio"],
    },
    "visiting_faculty": {
        "visiting_faculty_industry_academic": ["visiting_faculty", "visiting_faculty_industry_academic", "guest_faculty", "industry_academic_experts"],
    },
    "research": {
        "seed_money": ["seed_money"],
        "research_fellows_enrolled": ["research_fellows", "research_fellows_enrolled", "jrf", "srf", "post_doctoral_fellows", "research_associates"],
        "sponsored_research_projects_govt": ["sponsored_research_projects_govt", "govt_research_funding", "government_research_funding"],
        "sponsored_research_projects_non_govt": ["sponsored_research_projects_non_govt", "non_govt_research_funding", "non_government_research_funding"],
        "consultancy_royalty_revenue": ["consultancy_revenue", "royalty_revenue", "consultancy_royalty_revenue", "consultancy"],
        "executive_development_programs": ["executive_development_programs", "executive_development"],
        "research_funding_proposals_submitted": ["research_funding_proposals_submitted", "funding_proposals_submitted"],
        "research_funding_proposals_approved_active": ["research_funding_proposals_approved_active", "funding_proposals_approved", "active_research_proposals"],
        "fellowships_national_international": ["fellowships", "fellowships_national_international"],
        "ipr_workshops_seminars": ["ipr_workshops", "ipr_seminars", "ipr_workshops_seminars"],
        "research_awards_recognitions": ["research_awards", "research_recognitions", "research_awards_recognitions"],
        "patents_published": ["patents_published", "patent_published"],
        "patents_granted": ["patents_granted", "patent_granted"],
        "ip_commercialisation": ["ip_commercialisation", "ip_commercialization", "commercialisation", "commercialization"],
        "h_index_scopus": ["h_index_scopus", "scopus_h_index"],
        "h_index_wos": ["h_index_wos", "wos_h_index"],
        "phds_awarded": ["phds_awarded", "phd_awarded", "ph_ds_awarded"],
        "research_papers_published": ["research_papers", "research_papers_published", "papers_published"],
        "books_chapters_published": ["books_and_chapters", "books_chapters_published", "books_and_chapters_published"],
        "conference_papers_published": ["conference_papers", "conference_papers_published"],
        "citations": ["citations", "citation_count"],
        "full_time_phd_scholars": ["full_time_phd_scholars", "phd_scholars"],
        "active_research_centres": ["active_research_centres", "research_centres"],
        "international_conferences_research_reports": ["international_conferences_research_reports", "research_reports"],
        "joint_research_international": ["joint_research", "joint_research_international", "international_collaboration"],
        "joint_conferences_international": ["joint_conferences", "joint_conferences_international"],
    },
    "faculty_fdp_corporate": {
        "corporate_training_programs": ["fdp_corporate", "corporate_training_programs", "corporate_training_programmes"],
        "corporate_training_revenue": ["corporate_training_revenue", "corporate_training_income"],
    },
    "student_entrepreneurship": {
        "entrepreneurship_training_25_hours": ["entrepreneurship_training_25_hours", "entrepreneurship_training", "25_hours_entrepreneurship"],
        "students_willing_business": ["entrepreneurship_status", "students_willing_business", "willing_to_start_business"],
        "startups_incubated": ["startups_incubated", "start_ups_incubated", "incubated_startups"],
    },
    "sac": {
        "extension_outreach_programs": ["extension_outreach_programs", "outreach_programs", "nss", "ncc", "red_cross", "yrc"],
        "students_extension_activities": ["extension_activity", "students_extension_activities"],
        "sports_cultural_awards": ["sports_cultural_awards", "sports_awards", "cultural_awards"],
        "clubs_technical_societies": ["technical_society", "technical_societies"],
        "students_clubs_societies_associations": ["club", "student_club", "student_society", "student_association", "students_clubs_societies_associations", "club_membership"],
        "gender_equity_activities": ["gender_equity_activity", "gender_equity_activities"],
        "professional_ethics_events": ["professional_ethics_event", "professional_ethics_events", "ethics_event"],
    },
    "p_and_d": {
        "extension_activity_awards": ["extension_activity_awards", "extension_awards"],
        "classrooms_tutorial_rooms": ["classrooms", "tutorial_rooms", "classrooms_tutorial_rooms"],
        "labs": ["labs", "laboratories"],
        "ict_enabled_classrooms": ["ict_enabled_classrooms", "ict_classrooms"],
        "student_computers": ["student_computers", "computers_students"],
        "office_faculty_computers": ["office_faculty_computers", "faculty_computers", "office_computers"],
    },
    "registrar_office": {
        "scholarships_freeships": ["scholarship_status", "scholarship_type", "scholarships", "freeships", "scholarships_freeships"],
        "full_tuition_fee_reimbursement": ["full_tuition_fee_reimbursement", "tuition_fee_reimbursement"],
        "girl_students_scholarships": ["girl_students_scholarships", "girl_scholarship", "female_scholarship"],
        "career_counselling_competitive_exams": ["career_counselling", "career_guidance", "competitive_exam_counselling"],
        "total_seats_filled": ["total_seats_filled", "seats_filled", "sanctioned_seats"],
        "reserved_category_seats": ["reserved_category_seats", "reserved_seats", "reservation_category"],
        "girl_students_enrolled": ["girl_students_enrolled", "female_students_enrolled"],
        "students_other_states": ["students_other_states", "other_states_students"],
        "students_other_countries": ["students_other_countries", "other_countries_students"],
        "first_generation_students": ["first_generation", "first_generation_students"],
        "first_generation_girl_students": ["first_generation_girl_students", "first_generation_girls"],
    },
    "alumni": {
        "alumni_contribution": ["alumni_contribution"],
        "alumni_entrepreneurship": ["alumni_entrepreneurship", "alumni_startup", "alumni_start_up"],
    },
    "finance": {
        "median_salary_ug": ["median_salary_ug", "ug_median_salary"],
        "median_salary_pg": ["median_salary_pg", "pg_median_salary"],
        "government_infrastructure_grants": ["government_infrastructure_grants", "govt_infrastructure_grants"],
        "non_government_infrastructure_grants": ["non_government_infrastructure_grants", "non_govt_infrastructure_grants"],
    },
    "library": {
        "library_usage_teachers": ["library_usage_teachers", "teacher_library_usage"],
        "library_usage_students": ["library_usage_students", "student_library_usage"],
    },
}


def _normalized_headers(row):
    if isinstance(row, pd.Series):
        return {normalize_text(key) for key in row.index}
    if isinstance(row, dict):
        return {normalize_text(key) for key in row.keys()}
    return set()


def _has_nonempty_value(row, normalized_header_names):
    if isinstance(row, pd.Series):
        data = row.to_dict()
    elif isinstance(row, dict):
        data = row
    else:
        return False

    wanted = {normalize_text(name) for name in normalized_header_names}
    for key, value in data.items():
        if normalize_text(key) not in wanted:
            continue
        try:
            if pd.isna(value):
                continue
        except (TypeError, ValueError):
            pass
        if str(value).strip() != "":
            return True
    return False


def _category_column_hits(module, row):
    headers = _normalized_headers(row)
    matches = []

    for category, hints in CATEGORY_COLUMN_HINTS.get(module, {}).items():
        normalized_hints = {normalize_text(hint) for hint in hints}
        exact = headers.intersection(normalized_hints)
        if exact:
            # A header is useful only when the corresponding cell has data.
            if _has_nonempty_value(row, exact):
                matches.append((category, 100, exact))

    return matches


def _international_category_matches(row):
    """Resolve the generic International sheet into student/faculty submodules."""
    person_type = normalize_text(get_column_value(row, ["person_type"]))
    activity = normalize_text(get_column_value(row, ["activity_type"]))
    direction = normalize_text(get_column_value(row, ["direction"]))
    duration = get_column_value(row, ["duration_weeks"])

    try:
        duration_weeks = float(duration) if duration else None
    except ValueError:
        duration_weeks = None

    results = []
    is_faculty = "faculty" in person_type or "teacher" in person_type
    is_student = "student" in person_type or not is_faculty
    is_inbound = direction in {"inbound", "in"}
    is_outbound = direction in {"outbound", "out"}

    if "summer" in activity or "winter" in activity or "internship" in activity:
        if is_student:
            results.append(("student_abroad_program", "summer_winter_overseas_internship"))
        return results

    if "dual degree" in activity or "dual degrees" in activity:
        if is_student:
            results.append(("student_abroad_program", "dual_degrees_international"))
        return results

    if "semester exchange" in activity:
        if is_faculty:
            if is_inbound:
                results.append(("faculty_exchange_abroad", "semester_exchange_faculty_inbound"))
            elif is_outbound:
                results.append(("faculty_exchange_abroad", "semester_exchange_faculty_outbound"))
        else:
            if is_inbound:
                results.append(("student_abroad_program", "semester_exchange_student_inbound"))
            elif is_outbound:
                results.append(("student_abroad_program", "semester_exchange_student_outbound"))
        return results

    if "exchange" in activity and duration_weeks is not None and duration_weeks <= 2:
        if is_faculty:
            if is_inbound:
                results.append(("faculty_exchange_abroad", "faculty_inbound_2_weeks"))
            elif is_outbound:
                results.append(("faculty_exchange_abroad", "faculty_outbound_2_weeks"))
        else:
            if is_inbound:
                results.append(("student_abroad_program", "student_exchange_inbound_2_weeks"))
            elif is_outbound:
                results.append(("student_abroad_program", "student_exchange_outbound_2_weeks"))

    return results


def _value_aware_matches(row, sheet_name):
    """Handle sheets where the same column means different submodules by value."""
    sheet = normalize_text(sheet_name)
    results = []

    if sheet in {"student activities", "student activity"}:
        activity = normalize_text(get_column_value(row, ["activity_type"]))
        if activity:
            if "professional ethics" in activity:
                results.append(("sac", "professional_ethics_events"))
            elif "gender equity" in activity:
                results.append(("sac", "gender_equity_activities"))
            elif any(term in activity for term in ("extension", "nss", "ncc", "red cross", "yrc")):
                results.append(("sac", "students_extension_activities"))
            elif any(term in activity for term in ("club", "technical societ", "sac", "cultural", "sport")):
                results.append(("sac", "students_clubs_societies_associations"))

    if sheet in {"placements", "placement"}:
        placement_status = normalize_text(get_column_value(row, ["placement_status"]))
        international = normalize_text(get_column_value(row, ["international_placement"]))
        competitive = normalize_text(get_column_value(row, ["competitive_exam"]))
        competitive_status = normalize_text(get_column_value(row, ["competitive_exam_status"]))
        higher_education = get_column_value(row, ["higher_education"])

        if placement_status:
            results.append(("placements", "students_to_be_placed"))
        if higher_education.strip():
            results.append(("placements", "students_to_go_higher_education"))
        if competitive_status:
            results.append(("placements", "students_to_appear_competitive_exams"))
            if "qualif" in competitive_status:
                results.append(("placements", "students_qualified_competitive_exams"))
        elif competitive:
            results.append(("placements", "students_to_appear_competitive_exams"))
        if international in {"yes", "y", "true", "1"} and "placed" in placement_status:
            results.append(("placements", "students_qualified_placed_international"))

    if sheet in {"counselling", "counseling"}:
        gender_mentoring = normalize_text(get_column_value(row, ["gender_mentoring"]))
        if gender_mentoring in {"yes", "y", "true", "1"}:
            results.append(("counselling", "girl_students_mentoring"))
        elif _has_nonempty_value(row, {"counsellor_id", "counselor_id", "counsellor", "counselor"}):
            results.append(("counselling", "number_of_counsellors"))

    if sheet in {"students", "student"}:
        internship_status = get_column_value(row, ["internship_status"])
        project_status = get_column_value(row, ["project_status"])
        placement_status = get_column_value(row, ["placement_status"])
        higher_education = get_column_value(row, ["higher_education_status", "higher_education"])
        competitive_exam = get_column_value(row, ["competitive_exam"])
        competitive_status = normalize_text(get_column_value(row, ["competitive_exam_status"]))

        if internship_status.strip() or project_status.strip():
            results.append(("placements", "internships_projects_practice_school"))
        if placement_status.strip():
            results.append(("placements", "students_to_be_placed"))
        if higher_education.strip():
            results.append(("placements", "students_to_go_higher_education"))
        if competitive_exam.strip() or competitive_status:
            results.append(("placements", "students_to_appear_competitive_exams"))
        if "qualif" in competitive_status and "not qualif" not in competitive_status:
            results.append(("placements", "students_qualified_competitive_exams"))

        year = normalize_text(get_column_value(row, ["year", "study_year", "current_year"]))
        graduation_year = get_column_value(row, ["graduation_year"])
        if graduation_year and year in {"4", "final year", "fourth year", "iv"}:
            results.append(("progression", "students_graduated_final_year"))

        international_program = normalize_text(get_column_value(row, ["international_program"]))
        if "dual degree" in international_program or "dual degrees" in international_program:
            results.append(("student_abroad_program", "dual_degrees_international"))
        elif "summer" in international_program or "winter" in international_program or "internship" in international_program:
            results.append(("student_abroad_program", "summer_winter_overseas_internship"))
        elif "exchange" in international_program:
            results.append(("student_abroad_program", "semester_exchange_student_outbound"))

    return list(dict.fromkeys(results))


def detect_category_matches(row, sheet_name="", forced_module=None):
    """Return all confident (module, category) matches for one row.

    A row may legitimately contain data for several modules.  The importer
    therefore returns multiple matches instead of forcing the whole row into
    one category.  Ambiguous or unmatched data returns an empty list and is
    stored as module=unclassified/category=unclassified.
    """
    explicit_module = detect_explicit_module(row)
    module_hint = normalize_module(forced_module) if forced_module else None

    if forced_module and module_hint not in MODULES:
        module_hint = None

    value_matches = _value_aware_matches(row, sheet_name)
    if module_hint:
        value_matches = [item for item in value_matches if item[0] == module_hint]
    if value_matches:
        return value_matches

    # Explicit category/submodule is the strongest possible signal.
    if explicit_module or module_hint:
        module = explicit_module or module_hint
        explicit_category = detect_explicit_category(module, row)
        if explicit_category:
            return [(module, explicit_category)]

    explicit_value = get_column_value(
        row,
        ["sub-module", "sub module", "submodule", "category", "category name", "subtopic", "topic", "metric", "indicator", "parameter"],
    )
    if explicit_value:
        target = normalize_text(explicit_value)
        global_category = GLOBAL_CATEGORY_ALIASES.get(target)
        if global_category:
            for module, info in MODULES.items():
                if global_category in info.get("categories", {}):
                    if module_hint and module != module_hint:
                        return []
                    return [(module, global_category)]

    # International is intentionally value-aware because its Activity_Type,
    # Person_Type and Direction together define the actual submodule.
    if normalize_text(sheet_name) == "international":
        international = _international_category_matches(row)
        if module_hint:
            international = [item for item in international if item[0] == module_hint]
        if international:
            return international

    modules_to_check = [module_hint] if module_hint else list(MODULES.keys())
    matches = []

    for module in modules_to_check:
        for category, score, _ in _category_column_hits(module, row):
            matches.append((module, category, score))

    # A sheet name is only a hint.  Mixed sheets such as Faculty and Students
    # legitimately contain fields belonging to several modules, so never throw
    # away a valid category merely because the sheet has a generic name.

    # Remove duplicate category matches and return deterministic ordering.
    unique = {}
    for module, category, score in matches:
        unique[(module, category)] = max(score, unique.get((module, category), 0))

    return [
        (module, category)
        for (module, category), _score in sorted(
            unique.items(),
            key=lambda item: (item[0][0], item[0][1])
        )
    ]


def detect_module(row, sheet_name="", extra_text=""):
    """Detect a module only when structural evidence is reliable."""
    explicit = detect_explicit_module(row)
    if explicit:
        return explicit

    sheet_text = normalize_text(sheet_name)
    if sheet_text in SHEET_MODULE_ALIASES:
        return SHEET_MODULE_ALIASES[sheet_text]

    header_text = normalize_text(extra_text)
    structural_text = f"{sheet_text} {header_text}".strip()

    category_modules = set()
    for module, info in MODULES.items():
        for category_key, label in info.get("categories", {}).items():
            if normalize_text(category_key) in structural_text or normalize_text(label) in structural_text:
                category_modules.add(module)
                break

    if len(category_modules) == 1:
        return next(iter(category_modules))

    return None


def detect_sheet_category(module, row, sheet_name):
    matches = detect_category_matches(row, sheet_name, forced_module=module)
    if len(matches) == 1:
        return matches[0][1]
    return None


def detect_category(module, row, sheet_name=""):
    matches = detect_category_matches(row, sheet_name, forced_module=module)
    if len(matches) == 1:
        return matches[0][1]
    return None


# =========================================================
# CATEGORY-SPECIFIC ROW EXTRACTION
# =========================================================

COMMON_CONTEXT_COLUMNS = {
    "id", "student_id", "faculty_id", "record_id", "name", "gender",
    "department", "program", "year", "section", "semester", "academic_year",
    "admission_year", "graduation_year", "person_id", "person_type",
    "date_of_birth", "state", "category", "designation", "qualification",
}


def _category_relevant_headers(module, category):
    hints = CATEGORY_COLUMN_HINTS.get(module, {}).get(category, [])
    return {normalize_text(value) for value in hints}


SHEET_CONTEXT_COLUMNS = {
    "international": {
        "international_id", "person_type", "person_id", "activity_type",
        "direction", "country", "duration_weeks", "academic_year", "status",
    },
    "student activities": {
        "activity_id", "student_id", "activity_type", "club", "event",
        "role", "participation_status", "hours", "academic_year",
    },
    "student activity": {
        "activity_id", "student_id", "activity_type", "club", "event",
        "role", "participation_status", "hours", "academic_year",
    },
    "counselling": {
        "counselling_id", "student_id", "counsellor_id", "counselling_type",
        "sessions", "mentoring", "gender_mentoring", "status", "academic_year",
    },
    "counseling": {
        "counselling_id", "student_id", "counsellor_id", "counselling_type",
        "sessions", "mentoring", "gender_mentoring", "status", "academic_year",
    },
}

# Internal classification fields must never be stored as user data.
# They are used by the portal itself, not displayed as imported university fields.
INTERNAL_DATA_FIELDS = {
    "module",
    "module_key",
    "module_name",
    "module_no",
    "submodule",
    "sub_module",
    "sub-module",
    "category",
    "category_key",
    "category_name",
    "configured_category_key",
    "configured_target_header",
    "target_header",
}


SHEET_CATEGORY_EXTRA_COLUMNS = {
    "placements": {
        "students_to_be_placed": {"placement_id", "student_id", "company", "job_role", "package_lpa", "placement_status", "placement_year"},
        "students_to_go_higher_education": {"placement_id", "student_id", "higher_education", "placement_year"},
        "students_to_appear_competitive_exams": {"placement_id", "student_id", "competitive_exam", "placement_year"},
        "students_qualified_competitive_exams": {"placement_id", "student_id", "competitive_exam", "competitive_exam_status", "placement_year"},
        "students_qualified_placed_international": {"placement_id", "student_id", "company", "placement_status", "international_placement", "placement_year"},
    },
    "placement": {
        "students_to_be_placed": {"placement_id", "student_id", "company", "job_role", "package_lpa", "placement_status", "placement_year"},
        "students_to_go_higher_education": {"placement_id", "student_id", "higher_education", "placement_year"},
        "students_to_appear_competitive_exams": {"placement_id", "student_id", "competitive_exam", "placement_year"},
        "students_qualified_competitive_exams": {"placement_id", "student_id", "competitive_exam", "competitive_exam_status", "placement_year"},
        "students_qualified_placed_international": {"placement_id", "student_id", "company", "placement_status", "international_placement", "placement_year"},
    },
}


def build_category_row(row, module, category, sheet_name=""):
    """Keep identity/context + fields belonging to this submodule only."""
    if isinstance(row, pd.Series):
        items = row.to_dict().items()
    elif isinstance(row, dict):
        items = row.items()
    else:
        return {}

    relevant = _category_relevant_headers(module, category)
    normalized_sheet = normalize_text(sheet_name)
    relevant.update(
        normalize_text(value)
        for value in SHEET_CONTEXT_COLUMNS.get(
            normalized_sheet,
            set(),
        )
    )
    relevant.update(
        normalize_text(value)
        for value in SHEET_CATEGORY_EXTRA_COLUMNS.get(
            normalized_sheet,
            {},
        ).get(category, set())
    )
    output = {}

    for key, value in items:
        normalized_key = normalize_text(key)

        # Never carry portal classification metadata into the imported
        # university-data payload. Module/submodule information remains in
        # the records table for internal grouping, but these fields are not
        # part of the actual dataset shown to users.
        if normalized_key in INTERNAL_DATA_FIELDS:
            continue

        if normalized_key in relevant or normalized_key in COMMON_CONTEXT_COLUMNS:
            try:
                if pd.isna(value):
                    continue
            except (TypeError, ValueError):
                pass
            if str(value).strip() != "":
                output[str(key)] = value

    # Explicitly selected categories may use a generic Value column.  Keep the
    # row rather than producing an empty category record in that case.
    if not output:
        return {}

    return output


def classify_row(row, sheet_name="", upload_mode="mixed", target_module=None, target_category=None):
    """Classify one spreadsheet row without ever creating module/unclassified.

    For mixed imports, every confident submodule gets its own record.  When no
    submodule matches, the complete row is stored only as
    unclassified/unclassified.  A module with an unknown submodule is never
    stored as module/unclassified.
    """
    if upload_mode == "specific":
        module = normalize_module(target_module)
        category = normalize_category(target_category, module)
        if module in MODULES and category in MODULES[module].get("categories", {}):
            category_row = build_category_row(row, module, category, sheet_name)
            if not category_row:
                category_row = row.to_dict() if isinstance(row, pd.Series) else dict(row)
            return [(module, category, category_row)]
        return [("unclassified", "unclassified", row)]

    matches = detect_category_matches(row, sheet_name)
    if not matches:
        return [("unclassified", "unclassified", row)]

    classified = []
    for module, category in matches:
        category_row = build_category_row(row, module, category, sheet_name)
        if category_row:
            classified.append((module, category, category_row))

    if not classified:
        return [("unclassified", "unclassified", row)]

    return classified


# =========================================================
# SOURCE TYPE
# =========================================================

def detect_source_type(url):
    parsed = urlparse(url)

    host = (
        parsed.hostname
        or ""
    ).lower()

    path = (
        parsed.path
        or ""
    ).lower()

    if "docs.google.com/spreadsheets" in url.lower():
        return "google_sheets"

    if "drive.google.com" in host:
        return "google_drive"

    if (
        "1drv.ms" in host
        or "onedrive.live.com" in host
    ):
        return "other"

    if path.endswith(
        (".xlsx", ".xls")
    ):
        return "excel"

    if path.endswith(".csv"):
        return "csv"

    return "other"


# =========================================================
# CLEANING
# =========================================================

def clean_columns(columns):
    result = []
    used = {}

    for index, column in enumerate(
        columns,
        start=1
    ):

        name = str(
            column
        ).strip()

        if not name:
            name = f"Column_{index}"

        count = used.get(
            name,
            0
        ) + 1

        used[name] = count

        if count > 1:
            name = f"{name}_{count}"

        result.append(name)

    return result


def _json_value(value):

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    if hasattr(
        value,
        "isoformat"
    ):
        return value.isoformat()

    if isinstance(
        value,
        float
    ) and value.is_integer():
        return int(value)

    return str(value)


def _row_dict(row):
    return {
        str(key): _json_value(value)
        for key, value in row.items()
    }


# =========================================================
# CREATE DATASET
# =========================================================

def create_dataset(
    user_id,
    title,
    source_url,
    upload_mode="mixed",
    target_module=None,
    target_category=None,
):
    upload_mode = (
        upload_mode
        if upload_mode in {
            "mixed",
            "specific"
        }
        else "mixed"
    )

    target_module = normalize_module(
        target_module
    )

    if target_module not in MODULES:
        target_module = None
        target_category = None

    if target_category:
        target_category = normalize_category(
            target_category,
            target_module
        )

        if target_category not in MODULES[
            target_module
        ]["categories"]:
            target_category = None

    source_type = detect_source_type(
        source_url
    )

    connection = get_connection()

    upload_id = None

    try:

        cursor = connection.execute(
            """
            INSERT INTO uploads
            (
                uploaded_by,
                title,
                source_url,
                upload_method,
                source_type,
                upload_mode,
                target_module,
                target_category,
                status
            )
            VALUES
            (?, ?, ?, 'link', ?, ?, ?, ?, 'processing')
            """,
            (
                user_id,
                title or "Imported Dataset",
                source_url,
                source_type,
                upload_mode,
                target_module,
                target_category,
            ),
        )

        upload_id = cursor.lastrowid

        connection.execute(
            """
            INSERT INTO dataset_refresh_logs
            (
                upload_id,
                status,
                error_message
            )
            VALUES
            (?, 'started', ?)
            """,
            (
                upload_id,
                "Starting spreadsheet import.",
            ),
        )

        connection.commit()

        try:

            file_path, filename = download_spreadsheet(
                source_url
            )

            try:

                extension = (
                    Path(file_path)
                    .suffix
                    .lower()
                )

                if extension == ".csv":

                    dataframe = pd.read_csv(
                        file_path
                    )

                    sheets = {
                        "CSV": dataframe
                    }

                elif extension in {
                    ".xlsx",
                    ".xls",
                }:

                    sheets = pd.read_excel(
                        file_path,
                        sheet_name=None
                    )

                else:

                    raise ValueError(
                        "Only CSV, XLS and XLSX files are supported."
                    )

                total_rows = 0
                max_columns = 0

                for sheet_name, dataframe in sheets.items():

                    if dataframe is None:
                        continue

                    dataframe = dataframe.dropna(
                        how="all"
                    )

                    if dataframe.empty:
                        continue

                    dataframe.columns = clean_columns(
                        dataframe.columns
                    )

                    max_columns = max(
                        max_columns,
                        len(dataframe.columns)
                    )

                    column_index_by_name = {
                        str(column): index
                        for index, column
                        in enumerate(
                            dataframe.columns,
                            start=1
                        )
                    }

                    for column_index, column in enumerate(
                        dataframe.columns,
                        start=1
                    ):

                        dtype = "text"

                        if pd.api.types.is_numeric_dtype(
                            dataframe[column]
                        ):
                            dtype = "number"

                        elif pd.api.types.is_datetime64_any_dtype(
                            dataframe[column]
                        ):
                            dtype = "date"

                        connection.execute(
                            """
                            INSERT OR IGNORE INTO dataset_columns
                            (
                                upload_id,
                                column_index,
                                column_name,
                                data_type
                            )
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                upload_id,
                                column_index,
                                str(column),
                                dtype,
                            ),
                        )

                    header_text = " ".join(
                        str(column)
                        for column in dataframe.columns
                    )

                    sample_text = " ".join(
                        str(value)
                        for value in
                        dataframe.head(5)
                        .fillna("")
                        .astype(str)
                        .values
                        .flatten()
                    )

                    for row_number, (_, row) in enumerate(
                        dataframe.iterrows(),
                        start=2
                    ):

                        classified_rows = classify_row(
                            row,
                            sheet_name,
                            upload_mode=upload_mode,
                            target_module=target_module,
                            target_category=target_category,
                        )

                        # One spreadsheet row can legitimately feed more than
                        # one submodule (for example a Faculty row can contain
                        # FDP, Research and International Exchange fields).
                        # Each match becomes its own clean record.
                        for module, category, category_row in classified_rows:
                            connection.execute(
                                """
                                INSERT INTO records
                                (
                                    upload_id,
                                    module_key,
                                    category_key,
                                    sheet_name,
                                    row_number,
                                    row_data
                                )
                                VALUES (?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    upload_id,
                                    module,
                                    category,
                                    str(sheet_name),
                                    row_number,
                                    json.dumps(
                                        _row_dict(category_row),
                                        ensure_ascii=False
                                    ),
                                ),
                            )

                        # row_count represents source spreadsheet rows, while
                        # records can be larger because one row may be split
                        # into several submodule records.
                        total_rows += 1

                connection.execute(
                    """
                    UPDATE uploads
                    SET
                        status='completed',
                        row_count=?,
                        column_count=?,
                        error_message=NULL,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (
                        total_rows,
                        max_columns,
                        upload_id,
                    ),
                )

                connection.execute(
                    """
                    UPDATE dataset_refresh_logs
                    SET
                        status='completed',
                        row_count=?,
                        column_count=?,
                        error_message=?
                    WHERE upload_id=?
                    AND status='started'
                    """,
                    (
                        total_rows,
                        max_columns,
                        "Import completed successfully.",
                        upload_id,
                    ),
                )

                connection.commit()

                return (
                    upload_id,
                    True,
                    None
                )

            finally:

                try:
                    Path(file_path).unlink(
                        missing_ok=True
                    )
                except Exception:
                    pass

        except Exception as error:

            connection.rollback()

            error_message = str(error)

            connection.execute(
                """
                UPDATE uploads
                SET
                    status='failed',
                    error_message=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    error_message,
                    upload_id,
                ),
            )

            connection.execute(
                """
                UPDATE dataset_refresh_logs
                SET
                    status='failed',
                    error_message=?
                WHERE upload_id=?
                AND status='started'
                """,
                (
                    error_message,
                    upload_id,
                ),
            )

            connection.commit()

            return (
                upload_id,
                False,
                error_message
            )

    except Exception as error:

        connection.rollback()

        return (
            upload_id,
            False,
            str(error)
        )

    finally:

        connection.close()


# =========================================================
# UPLOADS
# =========================================================

def get_uploads():

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                u.*,
                users.name AS uploader_name,
                users.email AS uploader_email
            FROM uploads u
            LEFT JOIN users
                ON users.id = u.uploaded_by
            ORDER BY u.created_at DESC
            """
        ).fetchall()

        result = []

        for row in rows:

            item = dict(row)

            item["filename"] = item.get(
                "title"
            )

            item["uploader"] = item.get(
                "uploader_name"
            )

            result.append(item)

        return result

    finally:
        connection.close()


def get_all_uploads():
    return get_uploads()


def get_all_datasets():
    return get_uploads()


def get_user_uploads(user_id):

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT *
            FROM uploads
            WHERE uploaded_by=?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        connection.close()


def get_user_datasets(user_id):
    return get_user_uploads(user_id)


def get_upload(upload_id):

    connection = get_connection()

    try:

        row = connection.execute(
            """
            SELECT
                u.*,
                users.name AS uploader_name,
                users.email AS uploader_email
            FROM uploads u
            LEFT JOIN users
                ON users.id=u.uploaded_by
            WHERE u.id=?
            LIMIT 1
            """,
            (upload_id,),
        ).fetchone()

        return (
            dict(row)
            if row
            else None
        )

    finally:
        connection.close()


# =========================================================
# ROW DECORATOR
# =========================================================

def _decorate(row):

    item = dict(row)

    try:
        data = json.loads(
            item.get(
                "row_data"
            )
            or "{}"
        )
    except (
        TypeError,
        ValueError
    ):
        data = {}

    # Remove portal-only classification metadata from the actual dataset
    # payload. Module/category remain available on the record itself for
    # internal grouping, but must never become spreadsheet data columns.
    cleaned_data = {}
    for key, value in data.items():
        if normalize_text(key) in INTERNAL_DATA_FIELDS:
            continue
        cleaned_data[key] = value

    item["row_data"] = cleaned_data
    item["data"] = cleaned_data

    item["module"] = item.get(
        "module_key"
    )

    item["category"] = item.get(
        "category_key"
    )

    item["filename"] = item.get(
        "title"
    )

    item["uploader"] = item.get(
        "uploader_name"
    )

    return item


# =========================================================
# DATA ACCESS
# =========================================================

def get_dataset_rows(
    upload_id,
    module=None,
    category=None
):

    query = """
        SELECT
            r.*,
            u.title,
            u.source_url,
            u.uploaded_by,
            users.name AS uploader_name,
            users.email AS uploader_email
        FROM records r
        JOIN uploads u
            ON u.id=r.upload_id
        LEFT JOIN users
            ON users.id=u.uploaded_by
        WHERE r.upload_id=?
    """

    params = [upload_id]

    if module:

        query += """
            AND r.module_key=?
        """

        params.append(
            normalize_module(module)
        )

    if category:

        query += """
            AND r.category_key=?
        """

        params.append(
            normalize_category(category)
        )

    query += """
        ORDER BY
            r.sheet_name,
            r.row_number
    """

    connection = get_connection()

    try:

        return [
            _decorate(row)
            for row in
            connection.execute(
                query,
                params
            ).fetchall()
        ]

    finally:
        connection.close()


def get_all_rows(
    module=None,
    category=None,
    upload_id=None,
    user_id=None
):

    query = """
        SELECT
            r.*,
            u.title,
            u.source_url,
            u.uploaded_by,
            users.name AS uploader_name,
            users.email AS uploader_email
        FROM records r
        JOIN uploads u
            ON u.id=r.upload_id
        LEFT JOIN users
            ON users.id=u.uploaded_by
        WHERE 1=1
    """

    params = []

    if module:

        query += """
            AND r.module_key=?
        """

        params.append(
            normalize_module(module)
        )

    if category:

        query += """
            AND r.category_key=?
        """

        params.append(
            normalize_category(category)
        )

    if upload_id:

        query += """
            AND r.upload_id=?
        """

        params.append(
            upload_id
        )

    if user_id:

        query += """
            AND u.uploaded_by=?
        """

        params.append(
            user_id
        )

    query += """
        ORDER BY
            u.created_at DESC,
            r.sheet_name,
            r.row_number
    """

    connection = get_connection()

    try:

        return [
            _decorate(row)
            for row in
            connection.execute(
                query,
                params
            ).fetchall()
        ]

    finally:
        connection.close()


def get_module_data(module_key):

    module_key = normalize_module(
        module_key
    )

    if module_key not in MODULES:
        return {}

    grouped = {
        key: []
        for key in
        MODULES[module_key]["categories"]
    }

    for row in get_all_rows(
        module=module_key
    ):

        category = row.get(
            "category"
        )

        if category:
            grouped.setdefault(
                category,
                []
            ).append(row)

    return grouped


def prepare_module_tables(grouped_data):

    tables = []

    for category_key, rows in grouped_data.items():

        columns = []

        for row in rows:

            for column in row.get(
                "data",
                {}
            ):

                if normalize_text(column) in INTERNAL_DATA_FIELDS:
                    continue
                if column not in columns:
                    columns.append(column)

        tables.append(
            {
                "key": category_key,
                "rows": rows,
                "columns": columns,
            }
        )

    return tables


# =========================================================
# NUMERIC REPORTING
# =========================================================

BLOCKED_NUMERIC_FIELDS = {
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
    "phone",
    "mobile",
    "pincode",
    "pin_code",
}


def is_meaningful_numeric(field):

    name = normalize_text(
        field
    ).replace(
        " ",
        "_"
    )

    if name in BLOCKED_NUMERIC_FIELDS:
        return False

    if name.endswith("_id"):
        return False

    if name.endswith("id"):
        return False

    return True


def numeric_averages(rows):

    totals = {}
    counts = {}

    for row in rows:

        for field, value in row.get(
            "data",
            {}
        ).items():

            if not is_meaningful_numeric(
                field
            ):
                continue

            try:

                number = float(
                    str(value)
                    .replace(",", "")
                    .replace("%", "")
                    .strip()
                )

            except (
                TypeError,
                ValueError
            ):
                continue

            totals[field] = (
                totals.get(
                    field,
                    0
                )
                + number
            )

            counts[field] = (
                counts.get(
                    field,
                    0
                )
                + 1
            )

    return {
        field: round(
            totals[field] /
            counts[field],
            2
        )
        for field in totals
        if counts[field]
    }


# =========================================================
# REPORT
# =========================================================

def build_module_report(
    module_key,
    grouped_data=None
):

    module_key = normalize_module(
        module_key
    )

    if module_key not in MODULES:

        return {
            "module_key": module_key,
            "module_name": module_key,
            "total_records": 0,
            "category_counts": {},
            "numeric_averages": {},
        }

    if grouped_data is None:
        grouped_data = get_module_data(
            module_key
        )

    rows = [
        row
        for values in grouped_data.values()
        for row in values
    ]

    return {
        "module_key": module_key,
        "module_name": MODULES[
            module_key
        ]["name"],
        "total_records": len(rows),
        "category_counts": {
            key: len(values)
            for key, values
            in grouped_data.items()
        },
        "numeric_averages": numeric_averages(
            rows
        ),
    }


def get_report():

    uploads = get_uploads()

    modules = []

    total_records = 0
    populated_categories = 0

    for key, info in MODULES.items():

        grouped = get_module_data(
            key
        )

        report = build_module_report(
            key,
            grouped
        )

        categories = []

        for cat_key, values in grouped.items():

            cat_name = info[
                "categories"
            ].get(
                cat_key,
                str(cat_key)
                .replace("_", " ")
                .title()
            )

            count = len(values)

            if count:
                populated_categories += 1

            categories.append(
                {
                    "key": cat_key,
                    "name": cat_name,
                    "count": count,
                }
            )

        total_records += report[
            "total_records"
        ]

        modules.append(
            {
                "key": key,
                "name": info["name"],
                "description": info["description"],
                "icon": info["icon"],
                "total_records": report[
                    "total_records"
                ],
                "categories": categories,
                "numeric_averages": [
                    {
                        "field": field,
                        "value": value,
                    }
                    for field, value
                    in report[
                        "numeric_averages"
                    ].items()
                ][:8],
            }
        )

    unclassified_count = len(
        get_all_rows(
            module="unclassified"
        )
    )

    return {
        "generated_at":
            pd.Timestamp.now().strftime(
                "%d %b %Y, %I:%M %p"
            ),

        "total_records":
            total_records,

        "total_uploads":
            len(uploads),

        "populated_modules":
            sum(
                1
                for module
                in modules
                if module[
                    "total_records"
                ] > 0
            ),

        "total_modules":
            len(MODULES),

        "populated_categories":
            populated_categories,

        "total_categories":
            sum(
                len(
                    module["categories"]
                )
                for module
                in modules
            ),

        "unclassified_records":
            unclassified_count,

        "modules":
            modules,

        "recent_uploads":
            uploads[:8],
    }


# =========================================================
# DELETE
# =========================================================

def delete_upload(upload_id):
    """Delete an upload and all dependent imported data safely."""
    connection = get_connection()
    try:
        exists = connection.execute(
            "SELECT 1 FROM uploads WHERE id=? LIMIT 1",
            (upload_id,),
        ).fetchone()
        if not exists:
            return False

        # Explicit child deletion makes this work even when an older database
        # schema does not have ON DELETE CASCADE.
        connection.execute("DELETE FROM records WHERE upload_id=?", (upload_id,))
        connection.execute("DELETE FROM dataset_columns WHERE upload_id=?", (upload_id,))
        connection.execute("DELETE FROM dataset_refresh_logs WHERE upload_id=?", (upload_id,))
        connection.execute("DELETE FROM uploads WHERE id=?", (upload_id,))
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()



def delete_user_upload(upload_id, user_id):
    """Delete only a dataset owned by the given user."""
    connection = get_connection()
    try:
        exists = connection.execute(
            "SELECT 1 FROM uploads WHERE id=? AND uploaded_by=? LIMIT 1",
            (upload_id, user_id),
        ).fetchone()
        if not exists:
            return False

        connection.execute("DELETE FROM records WHERE upload_id=?", (upload_id,))
        connection.execute("DELETE FROM dataset_columns WHERE upload_id=?", (upload_id,))
        connection.execute("DELETE FROM dataset_refresh_logs WHERE upload_id=?", (upload_id,))
        connection.execute(
            "DELETE FROM uploads WHERE id=? AND uploaded_by=?",
            (upload_id, user_id),
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()



# =========================================================
# RECLASSIFY EXISTING DATABASE DATA
# =========================================================

def reclassify_existing_records():
    """Repair mixed imports without destroying already-correct submodule records."""
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT
                r.id,
                r.module_key,
                r.category_key,
                r.sheet_name,
                r.row_data
            FROM records r
            INNER JOIN uploads u
                ON u.id = r.upload_id
            WHERE COALESCE(u.upload_mode, 'mixed') <> 'specific'
            """
        ).fetchall()

        changed = 0
        for row in rows:
            try:
                data = json.loads(row["row_data"] or "{}")
            except Exception:
                data = {}
            if not isinstance(data, dict):
                data = {}

            matches = detect_category_matches(
                data,
                row["sheet_name"] or "",
            )
            current = (
                row["module_key"],
                row["category_key"],
            )

            # If the existing pair is still supported by the row's fields,
            # leave it alone.  This is important for split Faculty/Student
            # records because their sheet name may be generic.
            if current in matches:
                continue

            if len(matches) == 1:
                detected_module, detected_category = matches[0]
                # Existing records with a real module but no valid submodule
                # are not allowed anymore: move the entire record to the
                # single unclassified bucket.
            elif not matches:
                detected_module, detected_category = "unclassified", "unclassified"
            else:
                # More than one possible category is ambiguous.  Do not guess.
                detected_module, detected_category = "unclassified", "unclassified"

            if (
                detected_module != row["module_key"]
                or detected_category != row["category_key"]
            ):
                connection.execute(
                    """
                    UPDATE records
                    SET module_key=?, category_key=?
                    WHERE id=?
                    """,
                    (
                        detected_module,
                        detected_category,
                        row["id"],
                    ),
                )
                changed += 1

        connection.commit()
        return changed
    finally:
        connection.close()
