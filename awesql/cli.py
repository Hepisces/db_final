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
from rich.syntax import Syntax
from pathlib import Path
from typer.models import OptionInfo

# Import refactored modules
from . import db
from . import visualizer
from . import checker
from . import text2sql

# --- Adapter for Python 3.12+ sqlite3 datetime handling ---
# This silences the DeprecationWarning by registering a modern adapter.
sqlite3.register_adapter(datetime, lambda val: val.isoformat())

app = typer.Typer(
    name="awesql",
    help="一个用于数据库交互、查询、可视化和AI辅助的强大CLI工具。",
    rich_markup_mode="markdown"
)
config_app = typer.Typer(name="config", help="管理AI功能的配置，如模型和DDL文件路径。")
app.add_typer(config_app)
console = Console()

DB_FILE = "visualization_demo.db"
DATA_DIR = "Smart_Home_DATA"
OUTPUT_DIR = Path("output")

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
        # 确保filepath是字符串
        filepath_str = str(filepath)
        
        if sys.platform == "win32":
            os.startfile(filepath_str)
        elif sys.platform == "darwin": # macOS
            subprocess.run(["open", filepath_str], check=True)
        else: # linux
            subprocess.run(["xdg-open", filepath_str], check=True)
        console.print(f"✅ Automatically opened [bold white]{filepath_str}[/bold white]")
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        console.print(f"[bold red]Could not automatically open file:[/bold red] {e}")
        console.print(f"Please find it at: {os.path.abspath(filepath_str)}")

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
    try:
        # First try with a specific format
        converted_series = pd.to_datetime(series_copy, format='%Y-%m-%d %H:%M:%S.%f', errors='coerce')
    except:
        # If that fails, fall back to automatic format detection
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

def visualize_and_save(query: str, df: pd.DataFrame, output_file: Path):
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
            # 确保输出目录存在（虽然应该已经在调用前创建了）
            OUTPUT_DIR.mkdir(exist_ok=True)
            
            # 将Path对象转换为字符串以供plotly使用
            output_path = str(output_file)
            
            fig.write_image(output_path, scale=2) # Increase scale for better resolution
            console.print(f"[green]✅ Visualization saved to [bold white]{output_path}[/bold white][/green]")
            open_file(output_path)
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

def _is_admin(username, password):
    """
    检查管理员凭据。
    优先使用环境变量，如果未设置则回退到默认值。
    """
    admin_user = os.environ.get("AWESQL_ADMIN_USER", "admin")
    admin_pass = os.environ.get("AWESQL_ADMIN_PASS", "123")
    if username == admin_user and password == admin_pass:
        return True
    console.print("[bold red]认证失败，请检查您的用户名和密码。[/bold red]")
    return False

@app.command()
def run(
    query: str = typer.Argument(..., help="要执行和可视化的SQL查询。"),
    username: str = typer.Option(None, "--user", "-u", help="执行修改性查询所需的管理员用户名。"),
    password: str = typer.Option(None, "--pass", "-p", help="执行修改性查询所需的管理员密码。", hide_input=True),
    db_name: str = typer.Option("project2025.db", "--db-name", help="要查询的数据库文件的名称。")
):
    """
    执行SQL查询，显示结果、查询计划，并为SELECT查询生成可视化图表。

    - **对于SELECT查询**: 同时显示查询计划、结果表格，并生成图表。
    - **对于修改性查询 (INSERT, UPDATE, DELETE)**: 需要管理员权限 (`--user`, `--pass`)。
    """
    if not db.db_exists(db_name):
        console.print(f"[bold yellow]警告: 数据库 '{db_name}' 不存在或为空。[/bold yellow]")
        console.print("请先使用 `import-data` 命令导入数据。")
        raise typer.Exit()

    # Sanitize query by removing trailing semicolons
    query = query.strip().rstrip(';')

    # Check if it's a read-only query
    is_read_only = is_read_only_query(query)

    if not is_read_only:
        console.print("[bold yellow]警告: 这似乎是一个修改性查询。[/bold yellow]")
        if not _is_admin(username, password):
            console.print("[bold red]错误: 修改性查询需要管理员权限。请提供正确的 --user 和 --pass。[/bold red]")
            raise typer.Exit(code=1)
        console.print("[green]管理员权限验证通过。[/green]")

    console.print(f"正在执行查询: [magenta]'{query}'[/magenta]...")

    # For non-select queries, we just execute them
    if not query.lower().strip().startswith("select"):
        try:
            with db.create_connection(db_name) as conn:
                conn.execute(query)
                conn.commit()
                changes = conn.total_changes
                console.print(f"[green]查询执行成功，影响了 {changes} 行。[/green]")
        except sqlite3.Error as e:
            console.print(f"[bold red]数据库错误: {e}[/bold red]")
        return

    # For SELECT queries, proceed with visualization
    result_df, plan_df = db.execute_query(query, db_name=db_name)

    if result_df is None:
        console.print("[bold red]查询执行失败，无法继续。[/bold red]")
        raise typer.Exit(code=1)
        
    # 1. Draw Query Plan
    if plan_df is not None and not plan_df.empty:
        visualizer.draw_query_plan(plan_df)
    else:
        console.print("[yellow]未能获取查询计划。[/yellow]")

    # 2. Print Results Table
    visualizer.print_results_table(result_df)
        
    # 3. Visualize and Save Chart using the interactive visualizer
    if not result_df.empty:
        # Create a safe filename from the query
        safe_filename = "".join(c if c.isalnum() else "_" for c in query)[:50]
        # 使用Path对象正确拼接路径
        output_file = OUTPUT_DIR / f"{safe_filename}.png"
        # 确保输出目录存在
        OUTPUT_DIR.mkdir(exist_ok=True)

        # Call the interactive visualizer from the visualizer module
        visualizer.visualize_query_result(result_df, query, output_file)
    else:
        console.print("[yellow]查询未返回数据，跳过图表生成。[/yellow]")

@app.command()
def tables(
    db_name: str = typer.Option("project2025.db", "--db-name", help="要检查的数据库文件的名称。")
):
    """
    列出数据库中所有的表。
    """
    if not db.db_exists(db_name):
        console.print(f"[bold yellow]警告: 数据库 '{db_name}' 不存在或为空。[/bold yellow]")
        console.print("请先使用 `import-data` 命令导入数据。")
        return

    console.print(f"正在从 [cyan]{db_name}[/cyan] 获取表列表...")
    table_names = db.get_table_names(db_name)

    if table_names is None:
        console.print("[bold red]无法检索到表。[/bold red]")
        return
    
    if not table_names:
        console.print("[yellow]数据库中没有找到任何表。[/yellow]")
        return
        
    table = Table(title=f"数据库 '{db_name}' 中的表", show_header=True, header_style="bold magenta")
    table.add_column("序号", style="dim", width=6)
    table.add_column("表名")

    for i, name in enumerate(table_names):
        table.add_row(str(i + 1), name)
    
    console.print(table)

@app.command()
def er(
    data_dir: Path = typer.Option(
        "Smart_Home_DATA",
        "--dir",
        "-d",
        help="包含DDL.sql文件的目录。",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
):
    """
    从 DDL 文件生成并显示数据库的 E-R (实体-关系) 图。
    """
    ddl_path = data_dir / "DDL.sql"
    output_path = OUTPUT_DIR / "er_diagram.html"
    
    # 确保输出目录存在
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    console.print(f"正在从 [cyan]{ddl_path}[/cyan] 生成 E-R 图...")
    visualizer.generate_er_diagram(str(ddl_path), str(output_path))

@app.command()
def import_data(
    data_dir: Path = typer.Option(
        "Smart_Home_DATA", 
        "--dir", 
        "-d", 
        help="包含DDL.sql和数据文件的目录。默认为 'Smart_Home_DATA'。",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    db_name: str = typer.Option("project2025.db", "--db-name", help="为数据库指定一个自定义名称。")
):
    """
    将SQL文件中的数据导入新数据库。
    此命令在导入前会重置数据库。
    """
    db.reset_db(db_name)
    
    try:
        with db.create_connection(db_name) as conn:
            if not db.create_tables(conn, str(data_dir)):
                console.print("[bold red]创建数据库表失败，导入中止。[/bold red]")
                return
            db.import_real_data(conn, str(data_dir))
        console.print(f"[bold green]所有数据已成功导入到 '{db_name}'。[/bold green]")
    except Exception as e:
        console.print(f"[bold red]数据导入期间出错: {e}[/bold red]")

@app.command()
def reset_db(
    username: str = typer.Option(..., "--user", "-u", help="管理员用户名。", prompt=True),
    password: str = typer.Option(..., "--pass", "-p", help="管理员密码。", prompt=True, hide_input=True),
    db_name: str = typer.Option("project2025.db", "--db-name", help="要删除的数据库文件的名称。")
):
    """(仅限管理员) 删除现有数据库文件以重新开始。"""
    if not _is_admin(username, password):
        return
    try:
        db.reset_db(db_name)
        # 成功删除数据库后，询问是否删除配置文件
        if os.path.exists(db.CONFIG_FILE):
            delete_config = typer.confirm(
                "数据库已删除。您是否也想删除配置文件 'awesql_config.json'？"
            )
            if delete_config:
                db.reset_config()
    except Exception as e:
        console.print(f"[bold red]重置数据库时出错: {e}[/bold red]")

@app.command()
def check(
    query: str = typer.Argument(..., help="要检查正确性的SQL查询。")
):
    """使用AI助手检查所提供SQL查询的正确性。"""
    console.print("正在检查SQL查询...")
    try:
        config = db.load_config()
        ddl_path = config.get("ddl_path")

        schema_content = ""
        if ddl_path and os.path.exists(ddl_path):
            with open(ddl_path, 'r', encoding='utf-8') as f:
                schema_content = f.read()
        
        result = checker.check_sql_query(query, schema_content)
        console.print(f"\n[bold green]AI检查结果:[/bold green]\n{result}")
    except Exception as e:
        console.print(f"[bold red]SQL查询检查失败: {e}[/bold red]")

@app.command()
def ask(
    question: str = typer.Argument(..., help="要转换为SQL的自然语言问题。")
):
    """将自然语言问题翻译成SQL查询。"""
    console.print(f"正在根据您的问题生成SQL: \"{question}\"")
    try:
        config = db.load_config()
        model_path = config.get("model_path")
        ddl_path = config.get("ddl_path")

        if not model_path or not ddl_path:
            console.print("[bold red]错误: 模型路径或DDL路径未配置。[/bold red]")
            console.print("请运行 [bold]'awesql config set-model-path'[/bold] 和 [bold]'awesql config set-ddl-path'[/bold]进行设置。")
            return

        sql_query = text2sql.generate_sql(question, ddl_path, model_path)
        
        if not sql_query:
            console.print("[bold red]无法生成SQL查询。请检查模型或问题。[/bold red]")
            return
            
        console.print("\n[bold green]🎉 生成的SQL查询:[/bold green]")
        syntax = Syntax(sql_query, "sql", theme="github-dark", line_numbers=True)
        console.print(syntax)

        if typer.confirm("是否要对此SQL进行检查?"):
            check(query=sql_query)
            
        # if typer.confirm("您想立即执行此查询吗?"):
        #     run(query=sql_query)
        console.print(f"生成成功, 可以使用[bold]'awesql run'[/bold]执行此查询")


    except Exception as e:
        console.print(f"[bold red]文本到SQL转换期间出错: {e}[/bold red]")

@config_app.command(name="set-model-path")
def set_model_path(
    path: Path = typer.Argument(
        ..., 
        help="本地HuggingFace模型目录的绝对路径。",
        exists=True, 
        file_okay=False, 
        dir_okay=True,
        resolve_path=True
    )
):
    """Sets and saves the local model path for the 'ask' command."""
    config = db.load_config()
    config["model_path"] = str(path)
    db.save_config(config)
    console.print(f"[green]模型路径已设为: [cyan]{path}[/cyan][/green]")

@config_app.command(name="set-ddl-path")
def set_ddl_path(
    path: Path = typer.Argument(
        ..., 
        help="用于AI辅助的DDL.sql文件的绝对路径。",
        exists=True,
        file_okay=True,
        dir_okay=False,
        resolve_path=True,
    )
):
    """Sets and saves the DDL file path for AI-powered commands."""
    config = db.load_config()
    config["ddl_path"] = str(path)
    db.save_config(config)
    console.print(f"[green]DDL文件路径已设为: [cyan]{path}[/cyan][/green]")

@config_app.command(name="show")
def show_config():
    """Displays the current configuration."""
    config = db.load_config()
    if not config:
        console.print("[yellow]未找到配置文件。请使用 `set-model-path` 或 `set-ddl-path` 创建。[/yellow]")
        return
    
    console.print("[bold]当前配置:[/bold]")
    for key, value in config.items():
        console.print(f"  [cyan]{key}[/cyan]: {value}")

# --- Utility Functions ---
def is_read_only_query(query: str) -> bool:
    """
    使用 sqlparse 检查查询是否只包含 SELECT 语句。
    """
    parsed = sqlparse.parse(query)
    for statement in parsed:
        # get_type() 返回语句的类型: 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'UNKNOWN'
        if statement.get_type() != 'SELECT':
            return False
    return True

if __name__ == "__main__":
    app() 