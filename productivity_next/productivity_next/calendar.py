import frappe
import json

@frappe.whitelist()
def get_custom_events(doctype, start=None, end=None, filters=None):
    # get_list applies the caller's permissions and builds the filter SQL safely
    # (this used to run SELECT * on any table named by the caller)
    filters = json.loads(filters) if filters else []
    events = frappe.get_list(doctype, filters=[f[1:4] for f in filters], fields=["*"], limit_page_length=0)
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
