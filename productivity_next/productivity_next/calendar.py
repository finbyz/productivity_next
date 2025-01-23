import frappe
import json

@frappe.whitelist()
def get_custom_events(doctype, start=None, end=None, filters=None):
    filters = json.loads(filters) if filters else []
    condition = ""

    for filter in filters:
        field = filter[1]
        operator = filter[2]
        value = filter[3]

        if operator.upper() == "BETWEEN" and isinstance(value, list) and len(value) == 2:
            # Properly format the BETWEEN clause
            condition += f" AND {field} BETWEEN '{value[0]}' AND '{value[1]}'"
        else:
            # Handle other operators
            condition += f" AND {field} {operator} '{value}'"
    query = f"""
        SELECT *
        FROM `tab{doctype}`
        WHERE 1=1{condition}
    """
    events = frappe.db.sql(query, as_dict=True)
    for event in events:
        if event.get('assignee'):
            try:
                first_name = event['assignee'].split('@')[0].split('.')[0].capitalize()
                event['title'] = f"({first_name}) {event.get('subject', '')} "
            except Exception as e:
                event['title'] = f"({event.get('assignee', 'No Owner')}) {event.get('subject', '')} ({event.get('assignee', 'No Owner')})"
        else:
            event['title'] = f"{event.get('subject')}"

        if event.get('completed_on'):
            event['exp_start_date'] = event.get('completed_on')
    return events
