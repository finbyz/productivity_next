import frappe

sql_query = """
    UPDATE `tabApplication Usage log` AS aul
    JOIN `tabProject Password Domains` AS ppd
    ON aul.domain = ppd.domain_name
    JOIN `tabProject Password` AS p
    ON ppd.parent = p.name
    SET aul.project = p.project;
"""
frappe.db.sql(sql_query)
frappe.db.commit()

sql_query = """
UPDATE `tabWork Intensity` AS wi
JOIN (
    SELECT aul.project, aul.from_time, wi.name, wi.time,
           ROW_NUMBER() OVER (PARTITION BY wi.name ORDER BY ABS(TIMESTAMPDIFF(SECOND, wi.time, aul.from_time))) AS rn
    FROM `tabWork Intensity` AS wi
    JOIN `tabApplication Usage log` AS aul
    WHERE aul.project IS NOT NULL
) AS nearest_log ON nearest_log.name = wi.name AND nearest_log.rn = 1
SET wi.project = nearest_log.project
WHERE wi.project IS NULL OR wi.project = '';
"""
frappe.db.sql(sql_query)
frappe.db.commit()



sql_query = """
UPDATE `tabScreen Screenshot Log` AS ssl
JOIN (
    SELECT aul.project, aul.from_time, ssl.name, ssl.time,
           ROW_NUMBER() OVER (PARTITION BY ssl.name ORDER BY ABS(TIMESTAMPDIFF(SECOND, ssl.time, aul.from_time))) AS rn
    FROM `tabScreen Screenshot Log` AS ssl
    JOIN `tabApplication Usage log` AS aul
    WHERE aul.project IS NOT NULL
) AS nearest_log ON nearest_log.name = ssl.name AND nearest_log.rn = 1
SET ssl.project = nearest_log.project
WHERE ssl.project IS NULL OR ssl.project = '';
"""
frappe.db.sql(sql_query)
frappe.db.commit()