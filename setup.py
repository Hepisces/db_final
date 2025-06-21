from setuptools import setup, find_packages

# Core dependencies
core_requires = [
    'typer[all]',
    'pandas',
    'sqlparse',
    'requests',
    'matplotlib',
    'seaborn',
    'rich',
    'plotly',
    'kaleido',
    'sqlparse',
    'pandas'
]

# Optional dependencies for ML/AI features
extras_require = {
    'AI': [
        'transformers',
        'torch',
        'sentencepiece',
        'accelerate'
    ]
}

setup(
    name="awesql",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=core_requires,
    extras_require=extras_require,
    entry_points={
        'console_scripts': [
            'awesql = awesql.cli:app',
        ],
    },
    author="Jiawei He & Lufan Han & Yiran Yan",
    description="A command-line tool to execute SQL queries and visualize the results and execution plan.",
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Hepisces/db_final",
)