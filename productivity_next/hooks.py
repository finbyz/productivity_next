from . import __version__ as app_version

app_name = "productivity_next"
app_title = "Productivity Next"
app_publisher = "Finbyz Tech Pvt Ltd"
app_description = "Productivity Next"
app_email = "info@finbyz.com"
app_license = "GPL 3.0"

on_session_creation = "productivity_next.session.on_session_creation"

# Includes in <head>
# ------------------
app_include_js = [
    "https://cdn.plot.ly/plotly-latest.min.js",
    "https://cdn.jsdelivr.net/npm/echarts/dist/echarts.min.js",
    "assets/productivity_next/productivity_next/setup.js",
]

from . import __version__ as app_version

app_name = "productivity_next"
app_title = "Productivity Next"
app_publisher = "Finbyz Tech Pvt Ltd"
app_description = "Productivity Next"
app_email = "info@finbyz.com"
app_license = "GPL 3.0"

on_session_creation = "productivity_next.session.on_session_creation"

doctype_js = {
    "Lead": "public/js/doctype_js/lead.js",
    "Customer": "public/js/doctype_js/customer.js",
    "Opportunity": "public/js/doctype_js/opportunity.js",
    "Auto Repeat": "public/js/doctype_js/auto_repeat.js",
    "Notification": "public/js/doctype_js/notification.js",
    "Task": "public/js/doctype_js/task.js",
}

doctype_calendar_js = {
    "Task": "overrides/task/task_calendar.js"
}

override_doctype_class = {
	"Notification": "productivity_next.productivity_next.override_doctype_class.notification.Notification",
	"Auto Repeat": "productivity_next.productivity_next.override_doctype_class.auto_repeat.AutoRepeat",
}

# Document Events
# ---------------
# Hook on document methods and events
before_migrate = ["productivity_next.schedule.create_auto_email_report","productivity_next.schedule.create_auto_email_report_weekly"]
doc_events = {
    "Contact": {
        "validate": "productivity_next.productivity_next.doc_events.contact.validate",
    },
    "Task": {
        "before_save": "productivity_next.productivity_next.doc_events.task.before_save",
        "on_update": "productivity_next.productivity_next.doc_events.task.validate"
    },
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "all": [
        "productivity_next.schedule.bg_employee_log_generation",
        "productivity_next.schedule.schedule_comments",
        "productivity_next.schedule.create_productify_work_summary_today",
        "productivity_next.schedule.set_challenge",
    ],
    "cron": {
        "0 1 * * *": [
            "productivity_next.schedule.create_productify_work_summary",
            "productivity_next.schedule.delete_productify_error_logs",
            "productivity_next.schedule.delete_screenshots",
            "productivity_next.schedule.delete_application_logs",
            "productivity_next.schedule.create_auto_email_report",
            "productivity_next.schedule.create_auto_email_report_weekly",
        ],
        "0 0 * * *": [
            "productivity_next.schedule.submit_timesheet_created_by_productify",
            "productivity_next.schedule.update_due_period",
        ],
        # "5 4 * * sun" :[
        #     "productivity_next.schedule.send_weekly_report",
        # ]
    },
}

fixtures = [
    {"dt": "Custom Field", "filters": [["module", "in", "Productivity Next"]]},
    {
        "dt": "Activity Type",
        "filters": [
            ["name", "in", ["Project", "Task", "Issue"]]
        ]
    },
    {"dt": "Role", "filters": [["name", "in", ["Productify Manager"]]]},
    {"dt": "Property Setter", "filters": [["module", "in", ["Productivity Next"]]]},
    ["Task"],
]

# Installation
# ------------

# before_install = "productivity_next.install.before_install"
after_install = "productivity_next.setup.install.after_install"


scheduler_events = {
    "all": [
        "productivity_next.schedule.bg_employee_log_generation",
        "productivity_next.schedule.schedule_comments",
        "productivity_next.schedule.create_productify_work_summary_today",
        "productivity_next.schedule.set_challenge",
    ],
    "cron": {
        "0 1 * * *": [
            "productivity_next.schedule.create_productify_work_summary",
            "productivity_next.schedule.delete_productify_error_logs",
            "productivity_next.schedule.delete_screenshots",
            "productivity_next.schedule.delete_application_logs",
            "productivity_next.schedule.create_auto_email_report",
            "productivity_next.schedule.create_auto_email_report_weekly"
        ],
        "0 0 * * *": [
            "productivity_next.schedule.submit_timesheet_created_by_productify",
        ],
        # "5 4 * * sun" :[
        #     "productivity_next.schedule.send_weekly_report",
        # ]
    },
}

