import frappe
from frappe import _
from frappe.utils import cint

from productivity_next.productivity_next.report.project_time_analysis.project_time_analysis import (
    get_data as report_get_data,
    get_columns as report_get_columns,
)

# ⚠️ Confirm this matches the actual fieldname on Employee master
DEPLOYABLE_FIELDNAME = "deployable"


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


MAX_TREE_DEPTH = 50


def _get_active_employees():
    """Every active Employee, fetched once, so the tree is built in memory."""
    return frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["name", "employee_name", "reports_to", DEPLOYABLE_FIELDNAME],
        order_by="employee_name",
    )


def _build_children_map(rows):
    """
    Map parent employee id -> list of direct reports.

    An employee whose `reports_to` points at an inactive/missing Employee is
    treated as a root, so nobody is lost when a manager leaves.
    """
    known = {r.name for r in rows}
    children_map = {}
    for row in rows:
        parent = row.reports_to if row.reports_to in known else None
        children_map.setdefault(parent, []).append(row)
    return children_map


def _build_deployable_map(rows):
    """employee_id -> bool(custom_deployable)"""
    return {r.name: bool(cint(r.get(DEPLOYABLE_FIELDNAME))) for r in rows}


def build_node(employee_id, employee_name, valid_employees=None, children_map=None,
               deployable_only=1, deployable_map=None, _depth=0, _seen=None):
    """
    Recursively build a hierarchy node from Employee.reports_to.

    Subscription only decides whether a *leaf* is worth showing. An employee who
    is not subscribed but who has subscribed people under them is kept, so the
    branch below them stays reachable instead of being cut off mid-chain.

    When deployable_only is set, the same pass-through rule applies to the
    Employee master's "deployable" checkbox: an employee only counts as a valid
    leaf if they are BOTH subscribed AND deployable, but a non-deployable manager
    with deployable people under them is still kept as a pass-through branch.

    Returns None when this node and its whole subtree are irrelevant.
    """
    if valid_employees is None:
        valid_employees = get_all_subscribed_employees()
    if children_map is None:
        children_map = _build_children_map(_get_active_employees())
    if deployable_map is None:
        deployable_map = {}

    valid = set(valid_employees or [])
    deployable_only = cint(deployable_only)
    _seen = _seen or frozenset()

    # reports_to cycles would otherwise recurse forever
    if employee_id in _seen or _depth > MAX_TREE_DEPTH:
        return None

    children = []
    for child in children_map.get(employee_id, []):
        node = build_node(
            child.name, child.employee_name, valid_employees, children_map,
            deployable_only, deployable_map,
            _depth + 1, _seen | {employee_id},
        )
        if node:
            children.append(node)

    is_subscribed = employee_id in valid
    is_deployable = deployable_map.get(employee_id, False)
    counts_as_leaf = is_subscribed and (not deployable_only or is_deployable)

    if not counts_as_leaf and not children:
        return None

    return {
        "id": employee_id,
        "name": employee_name,
        "subscribed": is_subscribed,
        "deployable": is_deployable,
        "children": children,
    }


def _find_node(tree, employee_id):
    for node in tree:
        if node["id"] == employee_id:
            return node
        found = _find_node(node.get("children", []), employee_id)
        if found:
            return found
    return None


@frappe.whitelist()
def get_team_tree(deployable_only=1):
    """
    Get the full team hierarchy.
    - Administrator / System Manager -> forest of every top-level employee
    - Anyone else -> the subtree rooted at their own Employee record

    deployable_only (default 1): when truthy, only employees with the Employee
    master "deployable" checkbox checked are included as leaves (managers with
    deployable people under them are still kept as pass-through branches).
    """
    deployable_only = cint(deployable_only)
    user = frappe.session.user
    valid_employees = get_all_subscribed_employees()

    if not valid_employees:
        return {"is_admin": False, "tree": []}

    rows = _get_active_employees()
    children_map = _build_children_map(rows)
    deployable_map = _build_deployable_map(rows)

    # Roots: no reports_to, or reports_to an employee who is no longer active
    forest = []
    for root in children_map.get(None, []):
        node = build_node(
            root.name, root.employee_name, valid_employees, children_map,
            deployable_only, deployable_map,
        )
        if node:
            forest.append(node)

    if is_admin_user(user):
        return {"is_admin": True, "tree": forest}

    emp = get_employee_for_user(user)
    if not emp:
        frappe.throw(_("No active Employee record is linked to your user account."))

    # Re-root the forest at this user, keeping their whole subtree intact
    own_node = _find_node(forest, emp)
    if not own_node:
        own_node = build_node(
            emp,
            frappe.db.get_value("Employee", emp, "employee_name"),
            valid_employees + [emp],
            children_map,
            deployable_only,
            deployable_map,
        )

    return {"is_admin": False, "tree": [own_node] if own_node else []}


def flatten_ids(node):
    """Flatten tree node to get all employee IDs"""
    ids = [node["id"]]
    for child in node.get("children", []):
        ids.extend(flatten_ids(child))
    return ids


@frappe.whitelist()
def get_subtree_ids(employee):
    """
    Every active employee at or below `employee` in the reports_to chain,
    at any depth. Used when a lead is selected and the whole team's data
    should be aggregated.
    """
    children_map = _build_children_map(_get_active_employees())

    ids = []
    stack = [(employee, 0)]
    seen = set()
    while stack:
        emp_id, depth = stack.pop()
        if emp_id in seen or depth > MAX_TREE_DEPTH:
            continue
        seen.add(emp_id)
        ids.append(emp_id)
        for child in children_map.get(emp_id, []):
            stack.append((child.name, depth + 1))

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
        employee_list = get_subtree_ids(employee)
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
def get_employees_data(
    employees,
    from_date,
    to_date,
    project=None,
    resource_based_project=0,
    hourly_based_project=0,
    show_daily_data=0,
    is_internal_project=0,
    show_deployment_rate=0,
):
    """
    Fetch rows for an explicit set of employees in a single report call.

    Unlike get_node_data(include_subtree=1), the caller decides exactly who is
    in the set, so leads can be included or excluded independently of the
    reports_to chain. Used by the quick-stat tiles.
    """
    if isinstance(employees, str):
        employees = frappe.parse_json(employees)

    employee_list = [e for e in (employees or []) if e]
    if not employee_list:
        return []

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