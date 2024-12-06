import frappe
import json

@frappe.whitelist()
def get_custom_events(doctype, start=None, end=None, filters=None):
    conditions = []
    if start and end:
        date_conditions = f"""
            (exp_start_date IS NULL OR exp_end_date IS NULL OR 
             (exp_start_date <= '{end}' AND exp_end_date >= '{start}'))
        """
        conditions.append(date_conditions)
    else:
        conditions.append("(exp_start_date IS NULL OR exp_end_date IS NULL)")
    if filters:
        if isinstance(filters, str):
            filters = json.loads(filters)
        if isinstance(filters, list):
            if len(filters) > 0 and len(filters[0]) == 5:
                field = filters[0][1]
                value = filters[0][3]
                conditions.append(f"`{field}` = '{value}'")
            elif len(filters) > 0 and len(filters[0]) == 3:
                field = filters[0][0]
                value = filters[0][2]
                conditions.append(f"`{field}` = '{value}'")            
        elif isinstance(filters, dict):
            for field, value in filters.items():
                conditions.append(f"`{field}` = '{value}'")
    condition_str = " AND ".join(conditions)
        
    query = f"""
        SELECT *
        FROM `tab{doctype}`
        WHERE {condition_str}
    """
    events = frappe.db.sql(query, as_dict=True)
    for event in events:
        if event.get('task_owner'):
            try:
                first_name = event['task_owner'].split('@')[0].split('.')[0].capitalize()
                event['title'] = f"{event.get('subject', '')} ({first_name})"
            except Exception as e:
                event['title'] = f"{event.get('subject', '')} ({event.get('task_owner', 'No Owner')})"
        else:
            event['title'] = f"{event.get('subject')}"
    return events