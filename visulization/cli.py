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

# --- Adapter for Python 3.12+ sqlite3 datetime handling ---
# This silences the DeprecationWarning by registering a modern adapter.
sqlite3.register_adapter(datetime, lambda val: val.isoformat())

app = typer.Typer()
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

def visualize_and_save(query: str, df: pd.DataFrame, output_file: str):
    """Infer query type, visualize results with a scientific style, and save to a file."""
    query_type = infer_query_type(query, df)
    console.print(f"\n[bold cyan]🖼️  Result Visualization[/bold cyan]")
    console.print(f"Inferred query type: [bold]{query_type}[/bold]")

    fig = None
    plot_template = "plotly_white"
    
    # Wrap the query and replace newlines with HTML breaks for Plotly
    chart_title = textwrap.fill(query, width=80).replace('\n', '<br>')

    if query_type == "时间序列":
        time_col = next((c for c in df.columns if 'time' in c.lower() or 'date' in c.lower()), None)
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if time_col and numeric_cols:
            df[time_col] = pd.to_datetime(df[time_col])
            fig = px.line(df.head(100), x=time_col, y=numeric_cols[0], title=chart_title, markers=True, template=plot_template)
            
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
    """Infer query type to select a suitable visualization method."""
    # (This function is largely the same as the one in app.py)
    formatted_query = sqlparse.format(query.strip(), keyword_case='upper')
    time_cols = [c for c in df.columns if 'time' in c.lower() or 'date' in c.lower()]
    if any(pd.api.types.is_datetime64_any_dtype(df[c]) for c in df.columns if c in time_cols):
        return "时间序列"
    if 'GROUP BY' in formatted_query or any(f in formatted_query for f in ['COUNT(', 'SUM(', 'AVG(']):
        return "聚合分析"
    if len(df.columns) == 2 and pd.api.types.is_numeric_dtype(df.iloc[:, 1]):
        return "类别分布"
    return "一般查询"


@app.command()
def run(
    query: str = typer.Argument(..., help="The SQL query to execute and visualize."),
    output: str = typer.Option("visualization.png", "--output", "-o", help="Output file name for the visualization image.")
):
    """
    Executes a SQL query, displays the plan and results in the terminal,
    and saves a visualization as an image file.
    """
    if not db_exists():
        console.print("[bold yellow]Warning: Database not found or is empty.[/bold yellow]")
        console.print("Please run the [bold cyan]import-data[/bold cyan] command first to load data.")
        return

    console.print(f"[bold]Executing Query:[/bold] [white]{query}[/white]")
    
    try:
        conn = create_connection()
        
        # 1. Query Plan
        plan_df = pd.read_sql_query(f"EXPLAIN QUERY PLAN {query}", conn)
        draw_query_plan(plan_df)
        
        # 2. Query Results
        result_df = pd.read_sql_query(query, conn)
        print_results_table(result_df)
        
        # 3. Visualization
        if not result_df.empty:
            visualize_and_save(query, result_df, output)
            
    except sqlite3.Error as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred:[/bold red] {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@app.command()
def import_data():
    """
    Creates a new database and imports data from the Smart_Home_DATA directory.
    If the database already exists, this command will do nothing. Use reset-db first if needed.
    """

    if db_exists():
        console.print("[yellow]Database already exists and contains data.[/yellow]")
        console.print("To re-import, please run [bold cyan]reset-db[/bold cyan] first.")
        return
        
    try:
        conn = create_connection()
        create_tables(conn)
        import_real_data(conn)
    except Exception as e:
        console.print(f"[bold red]Import process failed: {e}[/bold red]")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

@app.command()
def reset_db():
    """
    Deletes the existing database file, allowing for a clean import.
    """
    if os.path.exists(DB_FILE):
        console.print(f"Deleting existing database file: [cyan]{DB_FILE}[/cyan]...")
        os.remove(DB_FILE)
        console.print("[bold green]Database has been reset.[/bold green]")
    else:
        console.print("[yellow]No database file found to reset.[/yellow]")


if __name__ == "__main__":
    app() 