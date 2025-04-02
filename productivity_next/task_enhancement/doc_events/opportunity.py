import frappe
def on_update(doc, method):
 
    # Check if the Lead's status is one of the specified ones
    if doc.status in ["Lost", "Closed"]:
       
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
        
        company_name = ''
        
        if doc.opportunity_from == "Lead" and doc.party_name:
            # Fetch company name from Lead
            response = frappe.db.get_value("Lead", doc.party_name, "company_name")
            company_name = response or ""
        elif doc.opportunity_from == "Prospect" and doc.party_name:
            response = ""
            company_name = response or ""
        elif doc.opportunity_from == "Customer":
            # If Customer, use party_name as company name
            company_name = doc.party_name or ""
        
      
        subject = f"Follow-up {doc.title}"
        if company_name:
            subject += f" ({company_name})"    
        
        task = frappe.new_doc('Task')
        task.subject = subject
        task.status = "Open"
        task.exp_start_date = frappe.utils.nowdate()  # You can modify this based on your requirements
        task.expected_time = 0.5  # Example: 0.5 hours
        task.project = project  # Set the project from Productify Subscription
        task.type = task_type  # Set the task_type from Productify Subscription
        task.assignee = assignee
        task.opportunity = doc.name
        task.description = f"Auto-created due to status change to '{doc.status}'"

        # Save the task
        task.insert(ignore_permissions=True)
        frappe.db.commit()  

        # Optionally, send a notification
        frappe.msgprint("Task created successfully for Opportunity")
