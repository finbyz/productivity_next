import frappe

def get_fincall_data(conditions) -> frappe._dict:
    QUERY = F"""
    SELECT 
        calltype,
        COUNT(*) AS fincall_count,
        COALESCE(SUM(duration), 0) AS total_duration
    FROM `tabEmployee Fincall`
    {conditions} and (link_to != 'Company' or link_to is null)
    GROUP BY calltype
    """


    result = frappe.db.sql(
        QUERY,
        as_dict=True
    )
    
    return result