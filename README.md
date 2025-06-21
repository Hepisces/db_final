# AwesomeSQL (`awesql`)

`awesql` is a powerful, educational command-line tool designed to interact with databases. It allows users to execute SQL queries, visualize results, check syntax, and translate natural language into SQL.

Built with Python, Typer, and Rich, `awesql` provides a rich, terminal-first user experience.

## Core Features

-   **Centralized Configuration**: Easily manage paths to your local AI model and DDL file using the `awesql config` command group.
-   **Admin-Protected Database Management**: Securely import data and reset the database using administrator credentials.
-   **Execute & Visualize**: Run SQL queries and get instant visual feedback, including an annotated query plan and high-resolution charts.
-   **AI-Powered Query Assistant**:
    -   `check`: Get suggestions and corrections for your SQL queries.
    -   `ask`: Translate a natural language question into a full SQL query.
-   **Smart Context**: The `ask` and `check` commands automatically use the schema from the configured DDL path, ensuring high-quality, context-aware AI assistance.

## Installation

We recommend using Conda to manage your environment.

```bash
# 1. Create and activate a Conda environment
conda create -n awesql python=3.12 -y
conda activate awesql

# 2. Install the tool and its dependencies in editable mode
# The '.' refers to the current directory (project root).
pip install -e .
```

Installing in "editable" mode (`-e`) means any changes you make to the source code will be immediately effective without needing to reinstall.

## Standard Workflow

The recommended workflow is to first set your paths using the `config` command, then use the other commands to manage and query your data.

### 1. (One-Time Setup) Configure Paths

This is the most important first step. You need to tell `awesql` where to find your AI model and your database schema file.

**A. Set the DDL File Path**
This file is the source of truth for your database schema.
```bash
awesql config set-ddl-path /path/to/your/DDL.sql
```

**B. Set the Local AI Model Path**
This is required for the `ask` (Text-to-SQL) command.
```bash
awesql config set-model-path /path/to/your/local_sql_model
```

**C. Verify Configuration**
You can view your saved settings at any time.
```bash
awesql config show
```
*Expected Output:*
```
Current `awesql` Configuration:
  ddl_path: /path/to/your/DDL.sql
  model_path: /path/to/your/local_sql_model
```

### 2. Import the Database (Admin Only)

Once the DDL path is configured, an admin can create and populate the database. The tool automatically looks for data files (`.sql`) in the same directory as your configured `DDL.sql`.

```bash
# The tool will prompt for username and password if not provided.
awesql import-data
```

### 3. Query and Analyze (Public)

With the database imported, any user can run queries and use the AI assistant tools.

**A. Execute a Query**
```bash
awesql run "SELECT type, COUNT(*) FROM devlist GROUP BY type"
```

**B. Check a Query**
The tool automatically uses the configured DDL path for context.
```bash
awesql check "SELEC name FRM customer"
```

**C. Ask a Question**
The tool uses both the DDL context and the configured local AI model.
```bash
awesql ask "Find all customers who never placed an order"
```

### 4. Reset the Database (Admin Only)

To delete the database and start fresh, use the `reset-db` command.

```bash
awesql reset-db
```
After resetting, you must run `import-data` again to recreate the database. 