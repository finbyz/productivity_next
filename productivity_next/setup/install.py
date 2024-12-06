import os
import click
def after_install():
    try:
        os.system("bench enable-scheduler")
        click.secho("Scheduler Enabled",color="green")
        os.system("bench set-config pause_scheduler 0")
        os.system("bench config set-common-config -c pause_scheduler 0")
        click.secho("Scheduler Resumed",color="green")
    except Exception as e:
        click.secho("Failed to Enable Scheduler",color="red")
        click.secho(str(e),color="red")
        click.secho("Please Enable Scheduler Manually",color="red")
        click.secho("\tbench enable-scheduler",color="green")
        click.secho("\tbench config set-common-config -c pause_scheduler 0",color="green")