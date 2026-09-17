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
# EXPLICIT MODULE DETECTION
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



# =========================================================
# EXPLICIT CATEGORY DETECTION
# =========================================================

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
    categories = MODULES[module].get("categories", {})

    # Exact aliases first.
    aliases = CATEGORY_ALIASES.get(module, {})
    if target in aliases:
        return aliases[target]

    # Then conservative phrase matching.
    for key, label in categories.items():
        label_text = normalize_text(label)
        key_text = normalize_text(key)
        if target == key_text or target == label_text:
            return key

    return None



# =========================================================
# MODULE DETECTION
# =========================================================

def detect_module(row, sheet_name="", extra_text=""):
    """
    Detect a module conservatively.

    Priority:
      1. Explicit Module column
      2. Exact module name/alias in sheet name
      3. Exact configured submodule label/key in the header/sheet
      4. Strong module phrase in header/sheet
      5. Otherwise unclassified

    Row values are deliberately NOT used for weak module guessing; this avoids
    putting generic student/faculty rows into the wrong module.
    """
    explicit = detect_explicit_module(row)
    if explicit:
        return explicit

    sheet_text = normalize_text(sheet_name)
    header_text = normalize_text(extra_text)
    structural_text = f"{sheet_text} {header_text}".strip()

    # Exact displayed module name or normalized key in the sheet/header.
    for key, info in MODULES.items():
        key_text = normalize_text(key)
        name_text = normalize_text(info.get("name", key))
        if name_text and name_text in sheet_text:
            return key
        if key_text and key_text in sheet_text:
            return key

    # If a header contains a complete configured category label, its parent
    # module is unambiguous.
    category_hits = []
    for module_key, info in MODULES.items():
        for category_key, label in info.get("categories", {}).items():
            label_text = normalize_text(label)
            key_text = normalize_text(category_key)
            if (label_text and label_text in structural_text) or (key_text and key_text in structural_text):
                category_hits.append(module_key)
                break

    category_hits = list(dict.fromkeys(category_hits))
    if len(category_hits) == 1:
        return category_hits[0]

    # If the metric/category label is stored as a row value rather than a
    # header, accept only an exact configured label/key match.
    row_text_value = normalize_text(row_text(row))
    row_category_hits = []
    for module_key, info in MODULES.items():
        for category_key, label in info.get("categories", {}).items():
            label_text = normalize_text(label)
            key_text = normalize_text(category_key)
            if (label_text and label_text in row_text_value) or (key_text and key_text in row_text_value):
                row_category_hits.append(module_key)
                break
    row_category_hits = list(dict.fromkeys(row_category_hits))
    if len(row_category_hits) == 1:
        return row_category_hits[0]

    # Strong phrase matching only against sheet/header text.
    candidates = []
    for module_key, keywords in MODULE_KEYWORDS.items():
        score = 0
        strong_hit = False
        for keyword in keywords:
            keyword_text = normalize_text(keyword)
            if not keyword_text or keyword_text not in structural_text:
                continue
            if " " in keyword_text:
                score += 5
                strong_hit = True
            else:
                score += 1
        if strong_hit and score >= 5:
            candidates.append((score, module_key))

    candidates.sort(key=lambda item: item[0], reverse=True)
    if not candidates:
        return None
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None
    return candidates[0][1]



# =========================================================
# CATEGORY DETECTION
# =========================================================

def detect_category(module, row, sheet_name=""):
    """Detect a category conservatively and return its exact configured key."""
    module = normalize_module(module)
    if module not in MODULES:
        return None

    explicit = detect_explicit_category(module, row)
    if explicit:
        return explicit

    categories = MODULES[module].get("categories", {})
    sheet_text = normalize_text(sheet_name)
    row_values = normalize_text(row_text(row))

    # Header/structure matching is stronger than ordinary row values.
    header_values = []
    if isinstance(row, pd.Series):
        header_values = [normalize_text(k) for k in row.index]
    elif isinstance(row, dict):
        header_values = [normalize_text(k) for k in row.keys()]
    header_text = " ".join(header_values)
    structural_text = f"{sheet_text} {header_text}".strip()

    exact_hits = []
    for key, label in categories.items():
        key_text = normalize_text(key)
        label_text = normalize_text(label)
        if (label_text and label_text in structural_text) or (key_text and key_text in structural_text):
            exact_hits.append(key)

    if len(exact_hits) == 1:
        return exact_hits[0]

    # Match a complete metric label in the actual row only when it is very
    # specific. This supports sheets where the metric name is a cell value.
    row_exact_hits = []
    for key, label in categories.items():
        key_text = normalize_text(key)
        label_text = normalize_text(label)
        if (label_text and label_text in row_values) or (key_text and key_text in row_values):
            row_exact_hits.append(key)
    if len(row_exact_hits) == 1:
        return row_exact_hits[0]

    # Finally use word overlap, but require at least three meaningful words
    # and a unique winner. This prevents generic words like "students" from
    # deciding the submodule.
    candidates = []
    for key, label in categories.items():
        label_text = normalize_text(label)
        words = [w for w in re.findall(r"[a-z0-9]+", label_text) if len(w) > 3]
        if not words:
            continue
        structural_matches = sum(1 for word in words if word in structural_text)
        row_matches = sum(1 for word in words if word in row_values)
        score = structural_matches * 3 + row_matches
        if structural_matches >= 2 or row_matches >= 3:
            candidates.append((score, key))

    candidates.sort(key=lambda item: item[0], reverse=True)
    if not candidates:
        return None
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None
    return candidates[0][1]



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
                message
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

                        if upload_mode == "specific":
                            module = target_module

                            category = (
                                target_category
                                or detect_category(
                                    module,
                                    row,
                                    sheet_name
                                )
                            )

                        else:

                            module = detect_module(
                                row,
                                sheet_name,
                                header_text
                            )

                            category = None

                            if module:
                                category = detect_category(
                                    module,
                                    row,
                                    sheet_name
                                )

                        # Unknown data is explicitly stored as unclassified.
                        # It is NOT silently put under Academics.
                        if not module:
                            module = "unclassified"

                        if not category:
                            category = "unclassified"

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
                                    _row_dict(row),
                                    ensure_ascii=False
                                ),
                            ),
                        )

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
                        rows_imported=?,
                        columns_imported=?,
                        message=?
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
                    message=?
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

    item["row_data"] = data
    item["data"] = data

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
    """Reclassify only mixed-mode imports; preserve explicit specific imports."""
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

            detected_module = detect_module(data, row["sheet_name"] or "", " ".join(str(k) for k in data.keys()))
            detected_module = detected_module or "unclassified"
            detected_category = detect_category(detected_module, data, row["sheet_name"] or "")
            detected_category = detected_category or "unclassified"

            if detected_module != row["module_key"] or detected_category != row["category_key"]:
                connection.execute(
                    """
                    UPDATE records
                    SET module_key=?, category_key=?
                    WHERE id=?
                    """,
                    (detected_module, detected_category, row["id"]),
                )
                changed += 1

        connection.commit()
        return changed
    finally:
        connection.close()

