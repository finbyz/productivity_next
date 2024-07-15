import frappe

app_url_timeDiff_distinct = frappe.db.sql("""
select
url.employee_name,
url.date,
url.total_url_time,
app.total_application_time,
ROUND(((app.total_application_time - url.total_url_time) / app.total_application_time) * 100, 2) as difference_percentage
from (
select
employee_name,
DATE(from_time) as date,
ROUND(sum(duration)/3600, 2) as total_url_time
from `tabURL Access Log`
group by employee_name, DATE(from_time)
) as url
join (
select
employee_name,
DATE(date) as date,
ROUND(sum(duration)/3600, 2) as total_application_time
from `tabApplication Usage log`
where application_name = 'Google Chrome'
group by employee_name, DATE(date)
) as app
on url.employee_name = app.employee_name and url.date = app.date
""", as_dict=True)

app_url_timeDiff = frappe.db.sql("""
select
ROUND(
(
(SUM(app.total_application_time) - SUM(url.total_url_time))
/ SUM(app.total_application_time)
) * 100, 2
) as difference_percentage
from (
select
employee_name,
DATE(from_time) as date,
ROUND(sum(duration)/3600, 2) as total_url_time
from `tabURL Access Log`
group by employee_name, DATE(from_time)
) as url
join (
select
employee_name,
DATE(date) as date,
ROUND(sum(duration)/3600, 2) as total_application_time
from `tabApplication Usage log`
where application_name = 'Google Chrome'
group by employee_name, DATE(date)
) as app
on url.employee_name = app.employee_name and url.date = app.date
""", as_dict=True)

difference_percentage = app_url_timeDiff[0]['difference_percentage'] if app_url_timeDiff else 0
print(difference_percentage)