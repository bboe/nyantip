"""nyantip setup.py"""

import re
from codecs import open
from os import path

from setuptools import find_packages, setup

PACKAGE_NAME = "nyantip"
HERE = path.abspath(path.dirname(__file__))
with open(path.join(HERE, "README.md"), encoding="utf-8") as fp:
    README = fp.read()
with open(path.join(HERE, PACKAGE_NAME, "const.py"), encoding="utf-8") as fp:
    VERSION = re.search('__version__ = "([^"]+)"', fp.read()).group(1)

extras = {
    "lint": [
        "black",
        "flake8",
        "isort",
    ],
}

setup(
    author="Bryce Boe",
    author_email="bbzbryce@gmail.com",
    description="Nyancoin tip bot for Reddit.",
    entry_points={"console_scripts": [f"{PACKAGE_NAME}={PACKAGE_NAME}:main"]},
    extras_require=extras,
    install_requires=[
        "Jinja2",
        "mysqlclient",
        "PyYAML",
        "praw >= 4",
        "sqlalchemy",
        "pifkoin @ git+https://github.com/dpifke/pifkoin@master#egg=pifkoin",
    ],
    keywords="reddit api wrapper",
    license="GPL",
    long_description=README,
    name=PACKAGE_NAME,
    package_data={"": ["LICENSE"]},
    packages=find_packages(),
    project_urls={"Source Code": "https://github.com/bboe/nyantip"},
    python_requires="~=3.6",
    version=VERSION,
)
