# SQL Query Visualization CLI

This is a command-line tool to execute and visualize SQL queries on a smart home database, built with Python, Typer, and Rich.

It allows you to:
- Reset and import a database from external `.sql` data files, including the table schema (`DDL.sql`).
- Execute an SQL query from your terminal.
- View the query execution plan, annotated with human-readable explanations, directly in your console.
- See the query results formatted as a clean table (limited to the first 10 rows).
- Save a scientific-style, high-resolution visualization of the results (e.g., bar chart, line chart) as an image file and automatically open it.

## Design Philosophy

This tool was designed with modularity, flexibility, and user experience in mind for both technical and non-technical users.

-   **Command-Driven Interface**: The tool is structured around clear, distinct commands (`import-data`, `reset-db`, `run`) using the `Typer` library. This makes the functionality easy to discover and use.
-   **Data-Driven Schema**: The database schema is not hardcoded. It's loaded from an external `DDL.sql` file located in the `Smart_Home_DATA` directory. This allows for easy modification of the table structure without touching the Python source code.
-   **Explainable AI for Queries**: The query plan visualization doesn't just show the raw output. It enriches the plan with simple, clear explanations for each step (e.g., `SCAN`, `SEARCH`). This makes the tool valuable for database experts who want technical details, as well as for data analysts who can gain insights into query performance without deep knowledge of database internals.
-   **Terminal-First, Rich UX**: All output is designed to be clear and useful within the terminal. `Rich` is used for beautifully formatted tables and annotated trees. For graphical charts, `Plotly` generates high-quality images which are then automatically opened, providing immediate visual feedback without requiring a full GUI.

## Complete Workflow Example

This section walks you through the entire process from a clean slate.

### 1. Installation

First, ensure you have Python 3.7+ installed. It is highly recommended to work within a virtual environment.

```bash
# Create and activate a virtual environment (optional but recommended)
python -m venv .venv
source .venv/bin/activate 

# Install the required packages
pip install -r requirements.txt
```

### 2. Prepare Your Data

Make sure you have a directory named `Smart_Home_DATA` in the project root, and that it contains your `DDL.sql` file and the corresponding data files (`customer.sql`, `devlist.sql`, etc.).

### 3. Import the Database

This is the first operational step. This command will create a `visualization_demo.db` file and populate it with your data. The import process for large files may take a few minutes.

```bash
python visulization/cli.py import-data
```

You should see progress bars for the data files being imported.

### 4. Run a Simple Query

Let's start with a basic query to see the number of devices per area.

```bash
python visulization/cli.py run "SELECT area, COUNT(did) as device_count FROM devlist GROUP BY area"
```

**What to Expect:**
1.  The annotated query plan will be printed in the terminal.
2.  A table with the query results will be displayed.
3.  An image file named `visualization.png` will be saved to `visulization/output/` and automatically opened.

### 5. Run a More Complex Query with a Custom Output Name

Now, let's run a more complex query to find the top device types and save the chart with a specific name.

```bash
python visulization/cli.py run "SELECT type, COUNT(did) AS device_count FROM devlist GROUP BY type ORDER BY device_count DESC" -o device_types_distribution.png
```

This will perform the same steps, but the output file will be named `device_types_distribution.png`.

### 6. Reset and Re-import (If Needed)

If you modify your source data files or just want to start over, you can easily reset the database.

```bash
# Step 1: Delete the current database
python visulization/cli.py reset-db

# Step 2: Re-import the data
python visulization/cli.py import-data
``` 