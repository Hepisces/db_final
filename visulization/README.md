# SQL Query Visualization CLI

This is a command-line tool to execute and visualize SQL queries on a sample smart home database.

It allows you to:
- Execute an SQL query from your terminal.
- View the query execution plan rendered as a tree directly in your console.
- See the query results formatted as a clean table.
- Save a graphical visualization of the results (e.g., bar chart, line chart) as an image file.

## How to Use

### 1. Installation

First, ensure you have Python 3.7+ installed. Then, install the required packages using pip:

```bash
# It is recommended to use a virtual environment
pip install -r requirements.txt
```

### 2. Running a Query

To run the tool, use the `python visulization/cli.py` command, followed by the SQL query you want to execute, enclosed in quotes.

#### Basic Example:

This command will query the number of devices in each area.

```bash
python visulization/cli.py "SELECT area, COUNT(did) as device_count FROM devlist GROUP BY area"
```

**Output:**

You will see the following in your terminal:
1.  **Query Plan**: A tree structure showing how the database will execute the query.
2.  **Query Results**: A table with the areas and their corresponding device counts.
3.  **Visualization Confirmation**: A message indicating that a chart has been saved as `visualization.png`.

#### Specifying Output File

You can specify a different name for the output image using the `-o` or `--output` option.

```bash
python visulization/cli.py "SELECT type, COUNT(did) FROM devlist GROUP BY type" -o device_types.png
```
This will save the resulting bar chart to a file named `device_types.png`.

#### Time-Series Example

```bash
python visulization/cli.py "SELECT did, time, data FROM control WHERE did = 'device_001' AND time > datetime('now', '-1 day')" -o device_001_activity.png
```
This will generate a line chart showing the activity for `device_001` over the last day. 