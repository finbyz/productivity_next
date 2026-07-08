import frappe
from frappe import _
from frappe.utils import cint

from productivity_next.productivity_next.report.project_time_analysis.project_time_analysis import (
    get_data as report_get_data,
    get_columns as report_get_columns,
)


def is_admin_user(user=None):
    user = user or frappe.session.user
    return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def get_employee_for_user(user=None):
    user = user or frappe.session.user
    return frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")


def get_all_subscribed_employees():
    """
    Get all active employees from Productify Subscription's list_of_users child table.
    Returns list of employee IDs.

    NOTE: "Productify Subscription" is a Single DocType (only one instance ever
    exists, and its `name` equals the doctype name). Single DocTypes do NOT have
    their own SQL table, so frappe.get_all("Productify Subscription", ...) will
    not work as expected (it queries a "tabProductify Subscription" table that
    doesn't exist for Singles). Use frappe.get_single()/frappe.get_doc() instead,
    and pull the child table rows directly off the returned document.
    """
    employees = []

    try:
        # Check if the doctype exists first
        if not frappe.db.exists("DocType", "Productify Subscription"):
            # Fallback: get all active employees
            emp_list = frappe.get_all(
                "Employee",
                filters={"status": "Active"},
                fields=["name"],
                order_by="employee_name"
            )
            return [emp.name for emp in emp_list]

        # Load the Single doc directly (do NOT use frappe.get_all on a Single)
        subscription = frappe.get_single("Productify Subscription")

        if subscription and subscription.status == "Active":
            # list_of_users is the child table on the Single doc itself
            employees = [
                row.employee
                for row in (subscription.list_of_users or [])
                if row.employee and row.status == "Active"
            ]

        # If no employees found from subscription, fallback to all active employees
        if not employees:
            emp_list = frappe.get_all(
                "Employee",
                filters={"status": "Active"},
                fields=["name"],
                order_by="employee_name"
            )
            employees = [emp.name for emp in emp_list]

    except Exception as e:
        frappe.log_error(f"Error fetching subscribed employees: {str(e)}", "Project Time Analysis")
        # Fallback: get all active employees
        emp_list = frappe.get_all(
            "Employee",
            filters={"status": "Active"},
            fields=["name"],
            order_by="employee_name"
        )
        employees = [emp.name for emp in emp_list]

    return employees


def build_node(employee_id, employee_name, valid_employees=None):
    """
    Recursively build a team-hierarchy node from Employee.reports_to.
    Only includes employees that are in the valid_employees list (subscribed employees).
    """
    if valid_employees is None:
        valid_employees = get_all_subscribed_employees()

    if not valid_employees:
        return {
            "id": employee_id,
            "name": employee_name,
            "children": [],
        }

    # Get children who report to this employee AND are in the valid list
    children_rows = frappe.get_all(
        "Employee",
        filters={
            "reports_to": employee_id,
            "status": "Active",
            "name": ["in", valid_employees]
        },
        fields=["name", "employee_name"],
        order_by="employee_name",
    )

    return {
        "id": employee_id,
        "name": employee_name,
        "children": [build_node(c.name, c.employee_name, valid_employees) for c in children_rows],
    }


@frappe.whitelist()
def get_team_tree():
    """
    Get team hierarchy based on subscribed employees.
    - Administrator / System Manager -> full forest of every top-level team lead
    - Anyone else -> a single tree rooted at their own Employee record
    """
    user = frappe.session.user

    # Get all valid employees
    valid_employees = get_all_subscribed_employees()

    if not valid_employees:
        return {"is_admin": False, "tree": []}

    if is_admin_user(user):
        # Get top-level employees (no reports_to) from valid employees
        roots = frappe.get_all(
            "Employee",
            filters={
                "reports_to": ["in", ["", None]],
                "status": "Active",
                "name": ["in", valid_employees]
            },
            fields=["name", "employee_name"],
            order_by="employee_name",
        )

        # If no top-level employees found, get the highest in hierarchy
        if not roots:
            # Get all valid employees with their reports_to
            all_emps = frappe.get_all(
                "Employee",
                filters={
                    "status": "Active",
                    "name": ["in", valid_employees]
                },
                fields=["name", "employee_name", "reports_to"]
            )

            # Find employees whose reports_to is not in valid_employees (virtual top-level)
            emp_ids = [e.name for e in all_emps]
            roots_data = [e for e in all_emps if e.reports_to not in emp_ids or not e.reports_to]

            tree = [build_node(r.name, r.employee_name, valid_employees) for r in roots_data]
        else:
            tree = [build_node(r.name, r.employee_name, valid_employees) for r in roots]

        return {"is_admin": True, "tree": tree}

    # Non-admin: get their own employee record
    emp = get_employee_for_user(user)
    if not emp:
        frappe.throw(_("No active Employee record is linked to your user account."))

    if emp not in valid_employees:
        # If employee not in valid list, still show their own tree
        emp_name = frappe.db.get_value("Employee", emp, "employee_name")
        tree = [build_node(emp, emp_name, valid_employees)]
        return {"is_admin": False, "tree": tree}

    emp_name = frappe.db.get_value("Employee", emp, "employee_name")
    tree = [build_node(emp, emp_name, valid_employees)]
    return {"is_admin": False, "tree": tree}


def flatten_ids(node):
    """Flatten tree node to get all employee IDs"""
    ids = [node["id"]]
    for child in node.get("children", []):
        ids.extend(flatten_ids(child))
    return ids


def _build_filters(extra):
    """
    Build a filters dict identical in shape to what the original report's
    JS config sends, so report_get_data / report_get_columns behave
    exactly as they do inside the standard report view.
    """
    filters = frappe._dict(
        {
            "show_details": 1,
        }
    )
    filters.update(extra)
    return filters


@frappe.whitelist()
def get_columns(show_deployment_rate=0):
    """
    Re-uses the existing report's get_columns() untouched.
    """
    filters = _build_filters(
        {
            "show_employee": 1,
            "show_deployment_rate": cint(show_deployment_rate),
        }
    )
    return report_get_columns(filters)


@frappe.whitelist()
def get_node_data(
    employee,
    from_date,
    to_date,
    include_subtree=0,
    project=None,
    resource_based_project=0,
    hourly_based_project=0,
    show_daily_data=0,
    is_internal_project=0,
    show_deployment_rate=0,
):
    """
    Fetch rows for one node (employee) of the tree using the existing report.
    """
    include_subtree = cint(include_subtree)

    if include_subtree:
        # Get valid employees for subtree
        valid_employees = get_all_subscribed_employees()
        node = build_node(
            employee,
            frappe.db.get_value("Employee", employee, "employee_name"),
            valid_employees
        )
        employee_list = flatten_ids(node)
    else:
        employee_list = [employee]

    filters = _build_filters(
        {
            "from_date": from_date,
            "to_date": to_date,
            "employee": employee_list,
            "show_employee": 1,
            "project": project,
            "resource_based_project": cint(resource_based_project),
            "hourly_based_project": cint(hourly_based_project),
            "show_daily_data": cint(show_daily_data),
            "is_internal_project": cint(is_internal_project),
            "show_deployment_rate": cint(show_deployment_rate),
        }
    )

    return report_get_data(filters)


@frappe.whitelist()
def get_all_subscribed_employees_list():
    """
    Return list of all subscribed employees with their basic info.
    Used for the 'All Employees' view.
    """
    employees = []

    try:
        # Check if the doctype exists
        if not frappe.db.exists("DocType", "Productify Subscription"):
            # Fallback: get all active employees
            return frappe.get_all(
                "Employee",
                filters={"status": "Active"},
                fields=["name", "employee_name", "reports_to", "designation", "department"],
                order_by="employee_name"
            )

        # Load the Single doc directly (do NOT use frappe.get_all on a Single)
        subscription = frappe.get_single("Productify Subscription")

        if subscription and subscription.status == "Active":
            for row in (subscription.list_of_users or []):
                if row.employee and row.status == "Active":
                    emp = frappe.db.get_value(
                        "Employee",
                        row.employee,
                        ["name", "employee_name", "reports_to", "designation", "department"],
                        as_dict=1
                    )
                    if emp:
                        emp["user_id"] = row.user_id
                        employees.append(emp)

        # Fallback if no employees found
        if not employees:
            employees = frappe.get_all(
                "Employee",
                filters={"status": "Active"},
                fields=["name", "employee_name", "reports_to", "designation", "department"],
                order_by="employee_name"
            )

    except Exception as e:
        frappe.log_error(f"Error in get_all_subscribed_employees_list: {str(e)}", "Project Time Analysis")
        # Fallback
        employees = frappe.get_all(
            "Employee",
            filters={"status": "Active"},
            fields=["name", "employee_name", "reports_to", "designation", "department"],
            order_by="employee_name"
        )

    return employees