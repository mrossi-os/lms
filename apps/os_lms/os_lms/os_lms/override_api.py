import frappe


from lms.lms.api import get_sidebar_settings as _original_get_sidebar_settings
from lms.lms.api import get_lms_settings as _original_get_lms_settings


from lms.command_palette import (
    get_instructor_info,
    can_access_course,
    can_access_batch,
    can_access_job,
)


@frappe.whitelist(allow_guest=True)
def get_sidebar_settings():

    result = _original_get_sidebar_settings()
    if isinstance(result, dict):
        lms_settings = frappe.get_single("LMS Settings")
        for field in ("programs", "home", "search", "quizzes", "assignments"):
            result[field] = lms_settings.get(field)

    return result

@frappe.whitelist(allow_guest=True)
def get_lms_settings():
    result = _original_get_lms_settings()
    if isinstance(result, dict):
         result["ai_enabled"] = frappe.get_single("LMSA Settings").get("enabled")
         lms_settings = frappe.get_single("LMS Settings")
         result["trueskills_api_enabled"] = lms_settings.get("trueskills_api_enabled")
    return result


# region search_sqlite
@frappe.whitelist()
def search_sqlite(query: str):
    from os_lms.overrides.sqlite import CustomLearningSearch
    from lms.sqlite import LearningSearchIndexMissingError

    search = CustomLearningSearch()

    try:
        result = search.search(query)
    except LearningSearchIndexMissingError:
        return []

    return prepare_search_results_custom(result)


def prepare_search_results_custom(result: dict):
    from lms.command_palette import remove_duplicates

    groups = get_grouped_results_custom(result)

    out = []
    for key in groups:
        groups[key] = remove_duplicates(groups[key])
        groups[key].sort(key=lambda x: x.get("modified"), reverse=True)
        out.append({"title": key, "items": groups[key]})

    return out


def get_grouped_results_custom(result):
    roles = frappe.get_roles()
    groups = {}
    for r in result["results"]:
        doctype = r["doctype"]
        if doctype == "LMS Course" and can_access_course(r, roles):
            r["author_info"] = get_instructor_info(doctype, r)
            groups.setdefault("Courses", []).append(r)
        elif doctype == "LMS Batch" and can_access_batch(r, roles):
            r["author_info"] = get_instructor_info(doctype, r)
            groups.setdefault("Batches", []).append(r)
        elif doctype == "Job Opportunity" and can_access_job(r, roles):
            r["author_info"] = get_instructor_info(doctype, r)
            groups.setdefault("Job Opportunities", []).append(r)
        elif doctype == "LMS Program":
            groups.setdefault("Programs", []).append(r)
        elif doctype == "LMS Quiz":
            groups.setdefault("Quizzes", []).append(r)
        elif doctype == "LMS Assignment":
            groups.setdefault("Assignments", []).append(r)
    return groups


# endregion
