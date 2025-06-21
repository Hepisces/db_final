from setuptools import setup, find_packages

with open("requirements.txt") as f:
    required = f.read().splitlines()

setup(
    name="awesql",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=required,
    entry_points={
        'console_scripts': [
            'awesql = awesql.cli:app',
        ],
    },
    author="Jiawei He & Lufan Ha & Yiran Yan",
    description="A command-line tool to execute SQL queries and visualize the results and execution plan.",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Hepisces/db_final",
)