import frappe
def on_update(doc, method):
 
    # Check if the Lead's status is one of the specified ones
    if doc.status in ["Lost Quotation", "Do Not Contact", "Junk"]:
        # Fetch the default assignee from Productify Subscription
        # assignee = frappe.db.get_single_value('Productify Subscription', 'user_for_lost_lead_followup')
        
        result = frappe.db.sql("""
        SELECT 
            field,
            value
        FROM 
            `tabSingles`
        WHERE 
            doctype = 'Productify Subscription' 
            AND field IN (
                'default_marketing_project', 
                'task_type', 
                'user_for_lost_lead_followup'
            )
        """, as_dict=True)
        
        
        project = next((item['value'] for item in result if item['field'] == 'default_marketing_project'), None)
        task_type = next((item['value'] for item in result if item['field'] == 'task_type'), 'Lead Follow-up')  # Default to 'Lead Follow-up'
        assignee = next((item['value'] for item in result if item['field'] == 'user_for_lost_lead_followup'), None)
        
        # Create a Task for the Lead
        task = frappe.new_doc('Task')
        task.subject = f"Follow-up {doc.lead_name} {doc.company_name}"
        task.status = "Open"
        task.exp_start_date = frappe.utils.nowdate()  # You can modify this based on your requirements
        task.expected_time = 0.5  
        task.project = project  
        task.type = task_type  
        task.assignee = assignee
        task.lead = doc.name
        task.description = f"Auto-created due to status change to '{doc.status}'"

        # Save the task
        task.insert(ignore_permissions=True)
        frappe.db.commit()  # Ensure the task is committed to the database

        # Optionally, send a notification
        frappe.msgprint("Task created successfully for Lead")
