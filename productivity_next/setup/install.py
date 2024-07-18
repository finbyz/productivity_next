import frappe
import click

def after_install():
    if frappe.db.exists("Role", "Productivity API"):
        click.echo("Role 'Productivity API' already exists", err=True)
        return
    frappe.new_doc("Role").update(
        {
            "role_name": "Productivity API",
            "desk_access": 1,
            "permissions": [{"role": "Employee", "read": 1, "write": 1}],
        }
    ).insert()
    click.echo("Role 'Productivity API' created")
    