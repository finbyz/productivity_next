import os
from setuptools import setup, find_packages

install_requires = []
if os.path.exists("requirements.txt"):
	with open("requirements.txt") as f:
		install_requires = [line.strip() for line in f if line.strip() and not line.startswith("#")]

# get version from __version__ variable in productivity_next/__init__.py
from productivity_next import __version__ as version

setup(
	name="productivity_next",
	version=version,
	description="Productivity Next",
	author="Finbyz Tech Pvt Ltd",
	author_email="info@finbyz.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
