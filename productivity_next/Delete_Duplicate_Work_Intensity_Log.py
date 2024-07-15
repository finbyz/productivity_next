import frappe
counter = 0
work_intensity_logs_with_no_data = frappe.db.sql("""
    SELECT
        name
    FROM
        `tabWork Intensity`
    WHERE
        total_keystrokes + total_mouse_clicks + total_scroll = 0
""", as_dict=True)
for i in work_intensity_logs_with_no_data:
    frappe.db.delete('Work Intensity', i['name'])
    print(f"Deleted Work Intensity Log: {i['name']}")
    counter += 1

    if counter % 50 == 0:
        frappe.db.commit()

duplicate_work_intensity_logs = frappe.db.sql("""
select
    name as name_to_keep,
    employee,
    CAST(date_time AS DATETIME) as date_time,
    total_keystrokes,
    total_mouse_clicks,
    total_scroll,
    count(*) as count
from
    `tabWork Intensity`
group by
    employee, CAST(date_time AS DATETIME), total_keystrokes, total_mouse_clicks, total_scroll
having
    count(*) > 1
""", as_dict=True)

names_to_keep = [row['name_to_keep'] for row in duplicate_work_intensity_logs]
names_to_delete = frappe.db.sql(f"""
    SELECT name
    FROM `tabWork Intensity`
    WHERE (employee, CAST(date_time AS DATETIME), total_keystrokes, total_mouse_clicks, total_scroll) IN (
        SELECT employee, CAST(date_time AS DATETIME), total_keystrokes, total_mouse_clicks, total_scroll
        FROM `tabWork Intensity`
        GROUP BY employee, CAST(date_time AS DATETIME), total_keystrokes, total_mouse_clicks, total_scroll
        HAVING COUNT(*) > 1
    ) AND name NOT IN ({', '.join(['%s'] * len(names_to_keep))})
""", names_to_keep, as_dict=True)

log_counter = 0
for doc in names_to_delete:
    frappe.delete_doc('Work Intensity', doc['name'])
    print(f"Deleted Work Intensity Log: {doc['name']}")
    log_counter += 1

    if log_counter % 50 == 0:
        frappe.db.commit()
