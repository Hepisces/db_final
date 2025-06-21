import typer
import pandas as pd
import sqlite3
from contextlib import closing
import random
from datetime import datetime, timedelta
import plotly.express as px
import sqlparse
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

app = typer.Typer()
console = Console()

DB_FILE = "visualization_demo.db"

# --- Database and Mock Data Logic (Adapted from previous version) ---

def create_connection():
    """Create a database connection to the SQLite database."""
    return sqlite3.connect(DB_FILE)

def create_tables(conn):
    """Create tables based on the provided DDL."""
    ddl_script = """
    CREATE TABLE IF NOT EXISTS customer (uid VARCHAR NOT NULL PRIMARY KEY, label INTEGER);
    CREATE TABLE IF NOT EXISTS devlist (uid VARCHAR, did VARCHAR NOT NULL PRIMARY KEY, type VARCHAR, area VARCHAR, FOREIGN KEY (uid) REFERENCES customer(uid));
    CREATE TABLE IF NOT EXISTS control (uid VARCHAR, did VARCHAR NOT NULL, form VARCHAR NOT NULL, data VARCHAR NOT NULL, time TIMESTAMP NOT NULL, PRIMARY KEY (did, time, form, data), FOREIGN KEY (uid) REFERENCES customer(uid));
    CREATE TABLE IF NOT EXISTS devupdata (uid VARCHAR, did VARCHAR NOT NULL, time TIMESTAMP NOT NULL, data VARCHAR NOT NULL, PRIMARY KEY (did, time, data), FOREIGN KEY (uid) REFERENCES customer(uid));
    """
    with closing(conn.cursor()) as cursor:
        cursor.executescript(ddl_script)
    conn.commit()

def generate_mock_data(conn):
    """Generate and insert mock data into the database if it's empty."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM customer")
    if cursor.fetchone()[0] > 0:
        return # Data already exists

    console.print("[yellow]Database is empty. Generating mock data...[/yellow]")
    num_customers=10
    num_devices_per_customer=3
    num_events_per_device=100
    
    # ... (Rest of mock data generation logic is the same as before)
    customers = [(f"user_{i:03d}", random.randint(1, 5)) for i in range(num_customers)]
    cursor.executemany("INSERT INTO customer (uid, label) VALUES (?, ?)", customers)

    devices, device_id_counter = [], 0
    device_types = ['light', 'thermostat', 'camera', 'lock', 'sensor']
    areas = ['living_room', 'bedroom', 'kitchen', 'bathroom', 'office']
    for uid, _ in customers:
        for _ in range(num_devices_per_customer):
            did = f"device_{device_id_counter:04d}"
            devices.append((uid, did, random.choice(device_types), random.choice(areas)))
            device_id_counter += 1
    cursor.executemany("INSERT INTO devlist (uid, did, type, area) VALUES (?, ?, ?, ?)", devices)

    control_events, devupdata_events = [], []
    now = datetime.now()
    for uid, did, dev_type, area in devices:
        for _ in range(num_events_per_device):
            event_time = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
            form = random.choice(['app', 'voice', 'auto'])
            data_map = {
                'light': random.choice(['on', 'off', f"brightness_{random.randint(10,100)}"]),
                'thermostat': f"temp_{random.uniform(18.0, 25.0):.1f}",
            }
            data = data_map.get(dev_type, random.choice(['locked', 'unlocked', 'recording_on']))
            control_events.append((uid, did, form, data, event_time))
            if dev_type in ['thermostat', 'sensor', 'camera']:
                 update_data = f"status_{random.choice(['ok', 'offline', 'triggered'])}_{random.random():.2f}"
                 devupdata_events.append((uid, did, event_time, update_data))
    
    cursor.executemany("INSERT INTO control (uid, did, form, data, time) VALUES (?, ?, ?, ?, ?)", control_events)
    cursor.executemany("INSERT INTO devupdata (uid, did, time, data) VALUES (?, ?, ?, ?)", devupdata_events)
    conn.commit()
    console.print("[green]Mock data generated successfully![/green]")

# --- CLI Visualization Logic ---

def draw_query_plan(plan_df: pd.DataFrame):
    """Draw the query plan as a tree in the console using rich."""
    console.print("\n[bold cyan]📊 Query Plan[/bold cyan]")
    tree = Tree("Query Plan")
    nodes = {row['id']: tree.add(f"[green]ID:{row['id']}[/green] | {row['detail']}") for _, row in plan_df[plan_df['parent'] == 0].iterrows()}
    
    remaining_rows = plan_df[plan_df['parent'] != 0].copy()
    while not remaining_rows.empty:
        processed_in_pass = False
        for index, row in remaining_rows.iterrows():
            parent_id = row['parent']
            if parent_id in nodes:
                nodes[row['id']] = nodes[parent_id].add(f"[green]ID:{row['id']}[/green] | {row['detail']}")
                remaining_rows.drop(index, inplace=True)
                processed_in_pass = True
        if not processed_in_pass and not remaining_rows.empty:
             console.print("[red]Error: Could not reconstruct query plan tree. Orphan nodes found.[/red]")
             break
             
    console.print(tree)

def print_results_table(df: pd.DataFrame):
    """Print the query results as a table in the console using rich."""
    console.print("\n[bold cyan]📈 Query Results[/bold cyan]")
    if df.empty:
        console.print("[yellow]Query executed successfully, but returned no data.[/yellow]")
        return
        
    table = Table(show_header=True, header_style="bold magenta")
    for col in df.columns:
        table.add_column(col)
    
    for _, row in df.iterrows():
        table.add_row(*[str(item) for item in row])
        
    console.print(table)

def visualize_and_save(query: str, df: pd.DataFrame, output_file: str):
    """Infer query type, visualize results, and save to a file."""
    # (Visualization logic is similar to before, but saves file instead of showing)
    query_type = infer_query_type(query, df)
    console.print(f"\n[bold cyan]🖼️  Result Visualization[/bold cyan]")
    console.print(f"Inferred query type: [bold]{query_type}[/bold]")

    fig = None
    if query_type == "时间序列":
        time_col = next((c for c in df.columns if 'time' in c.lower() or 'date' in c.lower()), None)
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if time_col and numeric_cols:
            df[time_col] = pd.to_datetime(df[time_col])
            fig = px.line(df, x=time_col, y=numeric_cols[0], title="Time Series Analysis", markers=True)
            
    elif query_type in ["聚合分析", "类别分布"]:
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(exclude=['number']).columns.tolist()
        if numeric_cols and categorical_cols:
            fig = px.bar(df, x=categorical_cols[0], y=numeric_cols[0], title="Aggregation/Categorical Analysis")

    if fig:
        try:
            fig.write_image(output_file)
            console.print(f"[green]✅ Visualization saved to [bold white]{output_file}[/bold white][/green]")
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
    console.print(f"[bold]Executing Query:[/bold] [white]{query}[/white]")
    
    try:
        conn = create_connection()
        create_tables(conn)
        generate_mock_data(conn)

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

if __name__ == "__main__":
    app() 