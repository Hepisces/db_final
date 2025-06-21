import typer
import pandas as pd
import sqlite3
from contextlib import closing
import os
import random
from datetime import datetime, timedelta
import plotly.express as px
import sqlparse
import sys
import subprocess
import textwrap
from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.progress import track

# Import refactored modules
from . import db
from . import visualizer
from . import checker
from . import text2sql

# --- Adapter for Python 3.12+ sqlite3 datetime handling ---
# This silences the DeprecationWarning by registering a modern adapter.
sqlite3.register_adapter(datetime, lambda val: val.isoformat())

app = typer.Typer(
    help="awesql: A powerful CLI to run, visualize, and check SQL queries.",
    rich_markup_mode="markdown"
)
console = Console()

DB_FILE = "visualization_demo.db"
DATA_DIR = "Smart_Home_DATA"
OUTPUT_DIR = "visulization/output"

PLAN_EXPLANATIONS = {
    "SCAN": "全表扫描: 从头到尾读取表的每一行。对于大表，这可能效率不高。通常意味着没有使用索引。",
    "SEARCH": "索引搜索: 使用索引来直接定位和读取满足条件的行子集，这通常比全表扫描快得多。",
    "USING INDEX": "使用了命名索引。",
    "USING COVERING INDEX": "使用了覆盖索引: 查询所需的所有数据都包含在索引中，无需访问原始表，效率非常高。",
    "USE TEMP B-TREE FOR": "使用临时B树: 为排序(ORDER BY)或分组(GROUP BY)创建了一个临时内部索引。如果频繁发生，可考虑为相关列添加真实索引来优化。",
    "COMPOUND QUERY": "复合查询: 正在执行一个包含 UNION, EXCEPT, 或 INTERSECT 的查询。",
    "MATERIALIZE": "物化子查询: 将一个子查询的结果存储在一个临时表中。这通常在子查询结果需要被多次使用时发生。",
    "CO-ROUTINE": "使用协程: 将子查询作为协程运行，按需生成行，而不是一次性生成所有结果。这可以减少内存使用。"
}

def get_explanation(detail_str: str) -> str:
    """Finds a human-readable explanation for a query plan detail string."""
    for keyword, explanation in PLAN_EXPLANATIONS.items():
        if keyword in detail_str:
            return f" [dim italic]({explanation})[/dim italic]"
    return ""

# --- Database and Data Loading Logic ---

def create_connection():
    """Create a database connection to the SQLite database."""
    return sqlite3.connect(DB_FILE)

def create_tables(conn):
    """Create tables based on the DDL.sql file."""
    ddl_file_path = os.path.join(DATA_DIR, "DDL.sql")
    console.print(f"Reading table schema from [cyan]{ddl_file_path}[/cyan]...")
    try:
        with open(ddl_file_path, 'r', encoding='utf-8') as f:
            ddl_script = f.read()
        with closing(conn.cursor()) as cursor:
            cursor.executescript(ddl_script)
        conn.commit()
        console.print("[green]Tables created successfully.[/green]")
    except FileNotFoundError:
        console.print(f"[bold red]Error: DDL file not found at {ddl_file_path}. Cannot create tables.[/bold red]")
        raise
    except Exception as e:
        console.print(f"[bold red]An error occurred while creating tables: {e}[/bold red]")
        raise

def import_real_data(conn):
    """Import data from the real .sql files."""
    cursor = conn.cursor()
    
    # Order matters due to foreign keys
    sql_files = ['customer.sql', 'devlist.sql', 'control.sql', 'devupdata.sql']
    
    console.print(f"[yellow]Starting data import from [bold]{DATA_DIR}[/bold]...[/yellow]")
    
    for file_name in sql_files:
        file_path = os.path.join(DATA_DIR, file_name)
        console.print(f"Processing [cyan]{file_path}[/cyan]...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Use a progress bar for large files
                for line in track(f, description=f"Importing {file_name}..."):
                    # Clean up the line and execute
                    sql_statement = line.strip()
                    if sql_statement:
                        # Remove the "public." schema prefix for SQLite compatibility
                        sql_statement = sql_statement.replace("INSERT INTO public.", "INSERT INTO ")
                        cursor.execute(sql_statement)
            conn.commit()
            console.print(f"[green]Successfully imported {file_name}.[/green]")
        except FileNotFoundError:
            console.print(f"[bold red]Error: File not found at {file_path}. Please check the path.[/bold red]")
            raise
        except Exception as e:
            console.print(f"[bold red]An error occurred while importing {file_name}: {e}[/bold red]")
            raise
            
    console.print("[bold green]All data has been successfully imported![/bold green]")

def db_exists():
    """Check if the database file exists and is not empty."""
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        return False
    # Further check if tables are populated
    try:
        conn = create_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM customer")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except sqlite3.Error:
        return False

# --- CLI Visualization Logic ---

def draw_query_plan(plan_df: pd.DataFrame):
    """Draw the query plan as a tree in the console using rich, with explanations."""
    console.print("\n[bold cyan]📊 Query Plan[/bold cyan]")
    tree = Tree("[bold]Query Plan[/bold]")
    nodes = {}

    # First pass: add all nodes to the tree and dictionary
    for _, row in plan_df.iterrows():
        explanation = get_explanation(row['detail'])
        node_label = f"[green]ID:{row['id']}[/green] | {row['detail']}{explanation}"
        nodes[row['id']] = {'label': node_label, 'parent': row['parent'], 'children': []}

    # Second pass: build the tree structure
    root_nodes = []
    for node_id, node_data in nodes.items():
        parent_id = node_data['parent']
        if parent_id == 0:
            root_nodes.append(node_id)
        else:
            if parent_id in nodes:
                nodes[parent_id]['children'].append(node_id)

    # Recursive function to add nodes to the rich Tree
    def add_to_tree(tree_node, node_id):
        node_data = nodes[node_id]
        child_tree_node = tree_node.add(node_data['label'])
        for child_id in sorted(node_data['children']):
            add_to_tree(child_tree_node, child_id)

    # Build the tree from root nodes
    for root_id in sorted(root_nodes):
        add_to_tree(tree, root_id)
             
    console.print(tree)

def open_file(filepath):
    """Open a file in the default application for the current platform."""
    try:
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin": # macOS
            subprocess.run(["open", filepath], check=True)
        else: # linux
            subprocess.run(["xdg-open", filepath], check=True)
        console.print(f"✅ Automatically opened [bold white]{filepath}[/bold white]")
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        console.print(f"[bold red]Could not automatically open file:[/bold red] {e}")
        console.print(f"Please find it at: {os.path.abspath(filepath)}")

def print_results_table(df: pd.DataFrame):
    """Print the query results as a table in the console, limited to 10 rows."""
    console.print("\n[bold cyan]📈 Query Results[/bold cyan]")
    if df.empty:
        console.print("[yellow]Query executed successfully, but returned no data.[/yellow]")
        return
    
    total_rows = len(df)
    display_df = df
    if total_rows > 10:
        console.print(f"[yellow]Total rows: {total_rows}. Showing top 10.[/yellow]")
        display_df = df.head(10)
        
    table = Table(show_header=True, header_style="bold magenta")
    for col in display_df.columns:
        table.add_column(col)
    
    for _, row in display_df.iterrows():
        table.add_row(*[str(item) for item in row])
        
    console.print(table)

def prepare_df_for_plotting(df: pd.DataFrame, category_col: str, metric_col: str, limit: int = 15) -> pd.DataFrame:
    """Limit the number of categories for plotting, grouping the rest into 'Other'."""
    if len(df) > limit:
        console.print(f"[yellow]Chart has {len(df)} categories. Displaying top {limit - 1} and aggregating the rest into 'Other'.[/yellow]")
        df_sorted = df.sort_values(by=metric_col, ascending=False)
        
        df_top = df_sorted.head(limit - 1)
        df_other = df_sorted.iloc[limit - 1:]
        
        if not df_other.empty:
            other_sum = df_other[metric_col].sum()
            other_row = pd.DataFrame([{category_col: 'Other', metric_col: other_sum}])
            df_plot = pd.concat([df_top, other_row], ignore_index=True)
        else:
            df_plot = df_top # Should not happen if len > limit but as a safeguard
            
        return df_plot
    return df

def try_convert_to_datetime(series: pd.Series) -> pd.Series | None:
    """
    Attempts to convert a pandas Series to datetime, trying multiple formats.
    Handles standard datetime strings and numeric unix timestamps (s, ms, us, ns).
    """
    # 1. Try standard conversion first (for ISO formats etc.)
    # Make a copy to avoid SettingWithCopyWarning
    series_copy = series.copy()
    converted_series = pd.to_datetime(series_copy, errors='coerce')
    
    if not pd.api.types.is_datetime64_any_dtype(converted_series) or converted_series.isnull().all():
        # 2. If it fails or results in all NaT, and dtype is numeric, try unix timestamp conversion
        if pd.api.types.is_numeric_dtype(series_copy):
            # Check for plausible unix timestamp in nanoseconds, microseconds, or milliseconds.
            # 1.6e18 (ns) is around 2020. A simple check for large numbers.
            # We check the mean to avoid issues with a few outlier points.
            if series_copy.mean() > 1e12: 
                # Attempt conversion from nanoseconds, most likely for IoT data
                converted_series = pd.to_datetime(series_copy, unit='ns', errors='coerce')
            else: # Otherwise, assume seconds
                converted_series = pd.to_datetime(series_copy, unit='s', errors='coerce')
    
    # Return the series only if the conversion was successful for at least one value
    if pd.api.types.is_datetime64_any_dtype(converted_series) and not converted_series.isnull().all():
        return converted_series
    
    return None

def visualize_and_save(query: str, df: pd.DataFrame, output_file: str):
    """Infer query type, visualize results with a scientific style, and save to a file."""
    query_type_info = infer_query_type(query, df)
    query_type = query_type_info[0] if isinstance(query_type_info, tuple) else query_type_info
    
    console.print(f"\n[bold cyan]🖼️  Result Visualization[/bold cyan]")
    console.print(f"Inferred query type: [bold]{query_type}[/bold]")

    fig = None
    plot_template = "plotly_white"
    
    # Wrap the query and replace newlines with HTML breaks for Plotly
    chart_title = textwrap.fill(query, width=80).replace('\n', '<br>')

    if query_type == "时间序列":
        _, time_col, value_col = query_type_info
        
        # --- Smart Data Conversion ---
        # 1. Convert time column to datetime and clean up
        df[time_col] = try_convert_to_datetime(df[time_col])
        df.dropna(subset=[time_col], inplace=True)
        df = df.sort_values(by=time_col)

        # 2. Attempt to convert value column to numeric
        value_series_numeric = pd.to_numeric(df[value_col], errors='coerce')

        # 3. Decide plotting strategy based on value column type
        if not value_series_numeric.isnull().all(): # Case 1: Value column is NUMERIC
            console.print(f"Plotting numeric time series: [cyan]'{time_col}'[/cyan] vs [cyan]'{value_col}'[/cyan].")
            df['numeric_value'] = value_series_numeric
            df_plot = df.dropna(subset=['numeric_value'])
            if not df_plot.empty:
                fig = px.line(df_plot, x=time_col, y='numeric_value', title=chart_title, markers=True, template=plot_template)
                fig.update_yaxes(title_text=value_col) # Use original column name for y-axis title
                
                # Ensure X-axis shows proper datetime format
                fig.update_xaxes(
                    type='date',
                    tickformat='%Y-%m-%d %H:%M:%S',
                    title_text=time_col
                )
        
        else: # Case 2: Value column is CATEGORICAL
            console.print(f"Plotting categorical time series: [cyan]'{time_col}'[/cyan] vs [cyan]'{value_col}'[/cyan].")
            df_plot = df.dropna(subset=[value_col])

            if not df_plot.empty:
                # Create a mapping from category to integer
                categories = df_plot[value_col].astype(str).unique()
                category_map = {cat: i for i, cat in enumerate(categories)}
                
                # Apply the mapping to create a numeric column for plotting
                df_plot['numeric_value'] = df_plot[value_col].map(category_map)
                
                # Use a step chart (line_shape='hv') for clearer state transitions
                fig = px.line(df_plot, x=time_col, y='numeric_value', title=chart_title, markers=True, template=plot_template, line_shape='hv')
                
                # Update the y-axis to show the original string labels instead of numbers
                fig.update_yaxes(
                    tickvals=list(category_map.values()),
                    ticktext=list(category_map.keys()),
                    title_text=value_col
                )
                
                # Ensure X-axis shows proper datetime format
                fig.update_xaxes(
                    type='date',
                    tickformat='%Y-%m-%d %H:%M:%S',
                    title_text=time_col
                )

    elif query_type in ["聚合分析", "类别分布"]:
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=['number']).columns.tolist()
        if numeric_cols and categorical_cols:
            category_col = categorical_cols[0]
            metric_col = numeric_cols[0]
            df_plot = prepare_df_for_plotting(df, category_col, metric_col)
            fig = px.bar(df_plot, x=category_col, y=metric_col, title=chart_title, template=plot_template)

    if fig:
        fig.update_layout(
            title_font_size=16,
            font=dict(family="Arial, sans-serif", size=14, color="black"),
            xaxis_title_font_size=16,
            yaxis_title_font_size=16,
        )
        try:
            # Ensure the output directory exists
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            full_path = os.path.join(OUTPUT_DIR, output_file)
            
            fig.write_image(full_path, scale=2) # Increase scale for better resolution
            console.print(f"[green]✅ Visualization saved to [bold white]{full_path}[/bold white][/green]")
            open_file(full_path)
        except Exception as e:
            console.print(f"[red]Error saving visualization: {e}[/red]")
            console.print("[yellow]Please ensure you have the 'kaleido' package installed (`pip install kaleido`).[/yellow]")
    else:
        console.print("[yellow]No suitable visualization generated for this query type.[/yellow]")

def infer_query_type(query, df):
    """
    Infer query type to select a suitable visualization method.
    This version is more robust and attempts to parse date-like strings and numeric timestamps.
    Returns a tuple: (query_type, col1_name, col2_name) for plottable types.
    """
    formatted_query = sqlparse.format(query.strip(), keyword_case='upper')
    
    # --- 1. First check for Aggregation/Categorical queries by SQL syntax ---
    # This takes precedence over time series detection
    has_aggregation = ('GROUP BY' in formatted_query or 
                      any(f in formatted_query for f in ['COUNT(', 'SUM(', 'AVG(', 'MIN(', 'MAX(']))
    
    if has_aggregation:
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=['number']).columns.tolist()
        
        if numeric_cols and categorical_cols:
            console.print("Query contains GROUP BY or aggregation functions. Treating as aggregation analysis.")
            return "聚合分析"
    
    # --- 2. Check for Time Series ---
    # Skip columns that are clearly aggregation results
    skip_columns = [col for col in df.columns if any(agg in col.lower() for agg in 
                   ['count(', 'sum(', 'avg(', 'min(', 'max(', 'count', 'sum', 'avg'])]
    
    # Find a time column
    time_col_name = None
    for col_name in df.columns:
        # Skip aggregation result columns for time detection
        if col_name in skip_columns:
            continue
            
        if try_convert_to_datetime(df[col_name]) is not None:
            time_col_name = col_name
            break
            
    if time_col_name:
        # Found a time column. Find a suitable value column that is not the time column.
        value_cols = [col for col in df.columns if col != time_col_name]
        if value_cols:
            console.print(f"Found time column: '{time_col_name}'. Treating as time series.")
            return "时间序列", time_col_name, value_cols[0]

    # --- 3. Check for simple categorical distributions ---
    if len(df.columns) == 2 and pd.api.types.is_numeric_dtype(df.iloc[:, 1]):
        return "类别分布"

    # --- 4. Default to general query ---
    return "一般查询"

def _is_admin(username: str, password: str) -> bool:
    """Verifies admin credentials."""
    return username == "admin" and password == "123"

@app.command()
def run(
    query: str = typer.Argument(..., help="The SQL query to execute and visualize."),
    output: str = typer.Option("visualization.png", "--output", "-o", help="Output file name for the visualization image.")
):
    """
    (Public) Executes a SQL query, displays plan/results, and saves a visualization.

    This is the primary command for running SQL queries. It provides a comprehensive
    analysis, including the query execution plan and a visual representation of the
    results, which is automatically opened.
    """
    if not db.db_exists():
        console.print("[bold yellow]Database 'project2025.db' not found or is empty.[/bold yellow]")
        console.print("An admin must run the 'import-data' command first.")
        raise typer.Exit(code=1)

    console.print(f"[bold]Executing Query:[/bold] [white]{query}[/white]")
    
    conn = None  # Initialize conn to None
    try:
        conn = db.create_connection()
        
        # 1. Query Plan
        plan_df = pd.read_sql_query(f"EXPLAIN QUERY PLAN {query}", conn)
        visualizer.draw_query_plan(plan_df)
        
        # 2. Query Results
        result_df = pd.read_sql_query(query, conn)
        visualizer.print_results_table(result_df)
        
        # 3. Visualization
        if not result_df.empty:
            visualizer.visualize_and_save(query, result_df, output)
            
    except sqlite3.Error as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred:[/bold red] {e}")
    finally:
        if conn:
            conn.close()

@app.command()
def import_data(
    username: str = typer.Option(..., "--user", "-u", help="Admin username for this operation.", prompt=True),
    password: str = typer.Option(..., "--pass", "-p", help="Admin password.", prompt=True, hide_input=True),
    data_dir: str = typer.Argument("Smart_Home_DATA", help="Directory containing DDL.sql and data files.")
):
    """
    (Admin Only) Creates 'project2025.db' and imports data from a directory.

    This command initializes the database from a specified data directory. It requires
    the directory to contain a `DDL.sql` file for the schema. Upon successful
    import, it saves the directory path to be automatically used by the `ask` command.
    """
    if not _is_admin(username, password):
        console.print("[bold red]Authentication failed. Admin privileges required.[/bold red]")
        raise typer.Exit(code=1)

    if db.db_exists():
        console.print("[yellow]Database 'project2025.db' already exists.[/yellow]")
        console.print("To re-import, please run 'reset-db' first (Admin Only).")
        return
    
    conn = None
    try:
        conn = db.create_connection()
        db.create_tables(conn, data_dir)
        db.import_real_data(conn, data_dir)
        # On success, save the data directory path for future use by 'ask'
        db.save_config({'data_dir': os.path.abspath(data_dir)})
    except FileNotFoundError:
        console.print("[bold red]Import process failed because DDL.sql was not found.[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Import process failed: {e}[/bold red]")
    finally:
        if conn:
            conn.close()

@app.command()
def reset_db(
    username: str = typer.Option(..., "--user", "-u", help="Admin username for this operation.", prompt=True),
    password: str = typer.Option(..., "--pass", "-p", help="Admin password.", prompt=True, hide_input=True)
):
    """
    (Admin Only) Deletes the existing 'project2025.db' database file.

    This is a destructive operation that removes the database file, allowing for a clean
    re-import. It also requires admin privileges.
    """
    if not _is_admin(username, password):
        console.print("[bold red]Authentication failed. Admin privileges required.[/bold red]")
        raise typer.Exit(code=1)
    db.reset_db()

@app.command()
def check(
    query: str = typer.Argument(..., help="The SQL query to check for correctness and get suggestions.")
):
    """
    (Public) Checks an SQL query for correctness using an external AI service.

    This command sends the provided SQL query to an AI for analysis. It returns
    feedback on syntax errors and provides suggestions for correction.
    """
    console.print(f"[bold]Checking Query:[/bold] [white]{query}[/white]")
    console.print("\n[yellow]正在请求AI检查，请稍候...[/yellow]")
    
    suggestion = checker.check_sql_query(query)
    
    console.print("\n[bold cyan]🤖 AI 分析结果:[/bold cyan]")
    console.print(suggestion)

@app.command()
def ask(
    question: str = typer.Argument(..., help="The natural language question to convert to SQL.")
):
    """
    (Public) Converts a natural language question to an SQL query using a local AI model.

    This command uses a local Text-to-SQL model to translate your question into an
    SQL query. It **automatically** uses the database schema from the last successful
    `import-data` command, so no schema file needs to be specified manually.
    """
    console.print(f"[bold]Question:[/bold] [white]{question}[/white]")
    
    config = db.load_config()
    data_dir = config.get('data_dir')

    if not data_dir:
        console.print("[bold red]Error: No data source has been configured yet.[/bold red]")
        console.print("Please ask an admin to run the `import-data` command first.")
        raise typer.Exit(code=1)

    schema_path = os.path.join(data_dir, "DDL.sql")
    schema_content = ""
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_content = f.read()
        console.print(f"Automatically using schema from: [cyan]{schema_path}[/cyan]")
    except FileNotFoundError:
        console.print(f"[bold red]Error: Could not find 'DDL.sql' in the configured data source: '{data_dir}'[/bold red]")
        raise typer.Exit(code=1)

    sql_query = text2sql.generate_sql(question, schema_content)
    
    console.print("\n[bold green]🤖 Generated SQL Query:[/bold green]")
    console.print(f"[white]{sql_query}[/white]")

if __name__ == "__main__":
    app() 