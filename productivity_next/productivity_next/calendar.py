import frappe
import json

@frappe.whitelist()
def get_custom_events(doctype, start, end, filters=None):
    # Prepare the base query conditions
    conditions = [
        f"exp_start_date <= '{end}'",
        f"exp_end_date >= '{start}'"
    ]
    
    # Process additional filters
    if filters:
        try:
            # If filters is a string, convert to list or dict
            if isinstance(filters, str):
                filters = json.loads(filters)
            
            # Handle list-type filters
            if isinstance(filters, list):
                # Handle 5-element list format
                if len(filters) > 0 and len(filters[0]) == 5:
                    # Extract field and value: ['Task', 'project', '=', 'PROJ-0004', False]
                    field = filters[0][1]
                    value = filters[0][3]
                    conditions.append(f"`{field}` = '{value}'")
                elif len(filters) > 0 and len(filters[0]) == 3:
                    # Handle 3-element list format
                    field = filters[0][0]
                    value = filters[0][2]
                    conditions.append(f"`{field}` = '{value}'")
            
            # Handle dictionary-type filters
            elif isinstance(filters, dict):
                for field, value in filters.items():
                    conditions.append(f"`{field}` = '{value}'")
        
        except Exception as e:
            frappe.msgprint(f"Error processing filters: {str(e)}")
            frappe.msgprint(f"Filters type: {type(filters)}")
            frappe.msgprint(f"Filters content: {filters}")
    
    # Construct the full SQL query
    condition_str = " AND ".join(conditions)
        
    try:
        # Fetch events using a direct SQL query
        query = f"""
            SELECT *
            FROM `tab{doctype}`
            WHERE {condition_str}
        """
        
        events = frappe.db.sql(query, as_dict=True)

        # Modify event titles
        for event in events:
            if event.get('task_owner_'):
                try:
                    # Split email and capitalize first part
                    first_name = event['task_owner_'].split('@')[0].split('.')[0].capitalize()
                    event['title'] = f"{event.get('subject', '')} ({first_name})"
                except Exception as e:
                    # Fallback if email parsing fails
                    event['title'] = f"{event.get('subject', '')} ({event.get('task_owner_', 'No Owner')})"
        return events
    
    except Exception as e:
        frappe.msgprint(f"Error retrieving events: {str(e)}")
        return []