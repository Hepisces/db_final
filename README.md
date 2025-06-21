# AwesomeSQL (`awesql`)

`awesql` is a powerful, educational command-line tool designed to interact with databases. It allows users to not only execute SQL queries but also visualize their results and execution plans, and even get AI-powered feedback on their query syntax or translate natural language into SQL.

Built with Python, Typer, and Rich, `awesql` provides a rich, terminal-first user experience.

## Core Features

-   **Admin-Protected Database Management**: Securely import data and reset the database using administrator credentials.
-   **Execute & Visualize**: Run SQL queries and get instant visual feedback.
    -   View the query execution plan, annotated with human-readable explanations.
    -   See results formatted in a clean, readable table.
    -   Generate and automatically open high-resolution charts (bar, line, step charts).
-   **AI-Powered Query Assistant**:
    -   `check`: Get suggestions and corrections for your SQL queries from an AI service.
    -   `ask`: Translate a natural language question into a full SQL query using a local model.
-   **Smart Context**: The `ask` command automatically uses the schema from the last successful data import, eliminating the need to specify it manually.
-   **Modular and Extendable**: Built with a clean, modular architecture that is easy to understand and extend.

## Installation

It is highly recommended to work within a virtual environment.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`

# 2. Install the tool and its dependencies in editable mode
# The '.' refers to the current directory (project root).
pip install -e .
```

Installing in "editable" mode (`-e`) means any changes you make to the source code will be immediately effective without needing to reinstall.

## Workflow and Usage

The tool is structured around a single main command, `awesql`, with several sub-commands.

### 1. Prepare Your Data

Before you begin, you need a data directory containing your SQL files. By default, the tool looks for `Smart_Home_DATA`. This directory **must** contain:
-   `DDL.sql`: The file that defines the database table schema.
-   Your data files (e.g., `customer.sql`, `devupdata.sql`, etc.).

### 2. Import the Database (Admin Only)

This command creates and populates the `project2025.db` database. It is a protected operation requiring admin credentials. Upon success, it also saves the data directory path for the `ask` command to use automatically.

```bash
# The tool will prompt for username and password if not provided.
awesql import-data
```
You can also specify the user and a different data directory:
```bash
awesql import-data -u admin path/to/your/data_folder
```

### 3. Run a Query (Public)

Once the database is created, any user can run queries.

**Example:**
```bash
awesql run "SELECT type, COUNT(did) AS device_count FROM devlist GROUP BY type ORDER BY device_count DESC"
```
This will print the query plan, show the results table, and open a generated bar chart.

### 4. AI-Powered Assistance (Public)

#### Check a Query's Syntax

If you're unsure about a query, use the `check` command.

**Example:**
```bash
awesql check "SELEC name FRM customer"
```
The tool will return AI-powered analysis and corrections.

#### Ask a Question in Natural Language

Use the `ask` command to translate a question into SQL. It automatically uses the schema from the last `import-data` run.

**Prerequisite:** Ensure the local SQLCoder model is downloaded and placed in the project root as specified in the original `text2sql/demo.ipynb`.

**Example:**
```bash
awesql ask "Find all customers who never placed an order"
```
The tool will load the local model and print the generated SQL query.

### 5. Reset the Database (Admin Only)

To delete the database and start fresh, use the `reset-db` command. This is also a protected operation.

```bash
# The tool will prompt for the admin username and password.
awesql reset-db
```
After resetting, you must run `import-data` again to recreate the database. 