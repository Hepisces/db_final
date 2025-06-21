import sqlite3
import os
from contextlib import closing
from rich.console import Console
from rich.progress import track
from datetime import datetime
import json
import pandas as pd

# --- Adapter for Python 3.12+ sqlite3 datetime handling ---
sqlite3.register_adapter(datetime, lambda val: val.isoformat())

console = Console()

DB_FILE = "project2025.db"
CONFIG_FILE = "awesql_config.json"

# --- Config Management ---

def save_config(config_data: dict):
    """Saves configuration data to a JSON file."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        console.print(f"数据源配置已保存至 [cyan]{CONFIG_FILE}[/cyan].")
    except Exception as e:
        console.print(f"[bold red]保存配置失败: {e}[/bold red]")

def load_config() -> dict:
    """Loads configuration data from a JSON file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        console.print(f"[bold red]加载或解析配置文件失败 {CONFIG_FILE}: {e}[/bold red]")
        return {}

# --- Database and Data Loading Logic ---

def create_connection():
    """Create a database connection to the SQLite database."""
    return sqlite3.connect(DB_FILE)

def create_tables(conn, data_dir: str) -> bool:
    """
    Create tables based on the DDL.sql file from the specified directory.
    Returns True on success, False on failure.
    """
    ddl_file_path = os.path.join(data_dir, "DDL.sql")

    if not os.path.isfile(ddl_file_path):
        console.print(f"[bold red]错误: 在 '{ddl_file_path}' 未找到DDL文件。[/bold red]")
        console.print(f"请确保在数据目录 '{data_dir}' 中存在 'DDL.sql' 文件。")
        return False

    console.print(f"正在从 [cyan]{ddl_file_path}[/cyan] 读取表结构...")
    try:
        with open(ddl_file_path, 'r', encoding='utf-8') as f:
            ddl_script = f.read()
        with closing(conn.cursor()) as cursor:
            cursor.executescript(ddl_script)
        conn.commit()
        console.print("[green]数据表创建成功。[/green]")
        return True
    except Exception as e:
        console.print(f"[bold red]创建数据表时出错: {e}[/bold red]")
        return False

def import_real_data(conn, data_dir: str):
    """Import data from the .sql files found in the specified directory."""
    cursor = conn.cursor()
    
    # Order matters due to foreign keys
    sql_files = ['customer.sql', 'devlist.sql', 'control.sql', 'devupdata.sql']
    
    console.print(f"[yellow]正在从 [bold]{data_dir}[/bold] 开始导入数据...[/yellow]")
    
    for file_name in sql_files:
        file_path = os.path.join(data_dir, file_name)
        if not os.path.exists(file_path):
            console.print(f"[yellow]警告: 在 '{data_dir}' 中未找到数据文件 [cyan]{file_name}[/cyan]。正在跳过。[/yellow]")
            continue
        
        console.print(f"正在处理 [cyan]{file_path}[/cyan]...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in track(f, description=f"正在导入 {file_name}..."):
                    sql_statement = line.strip()
                    if sql_statement:
                        sql_statement = sql_statement.replace("INSERT INTO public.", "INSERT INTO ")
                        cursor.execute(sql_statement)
            conn.commit()
            console.print(f"[green]成功导入 {file_name}。[/green]")
        except Exception as e:
            console.print(f"[bold red]导入 {file_name} 时出错: {e}[/bold red]")
            # Continue with the next file
            
    console.print("[bold green]所有可用数据均已成功导入！[/bold green]")

def db_exists():
    """Check if the database file exists."""
    return os.path.exists(DB_FILE)

def execute_query(query: str):
    """
    Executes a SQL query and its EXPLAIN QUERY PLAN.
    Returns a tuple of (result_df, plan_df).
    Returns (None, None) on error.
    """
    try:
        with create_connection() as conn:
            plan_df = pd.read_sql_query(f"EXPLAIN QUERY PLAN {query}", conn)
            result_df = pd.read_sql_query(query, conn)
            return result_df, plan_df
    except sqlite3.Error as e:
        console.print(f"[bold red]数据库错误: {e}[/bold red]")
        return None, None
    except Exception as e:
        console.print(f"[bold red]发生未知错误: {e}[/bold red]")
        return None, None

def reset_db():
    """
    Deletes the existing database file, allowing for a clean import.
    """
    if os.path.exists(DB_FILE):
        console.print(f"正在删除现有数据库文件: [cyan]{DB_FILE}[/cyan]...")
        os.remove(DB_FILE)
        console.print("[bold green]数据库已重置。[/bold green]")
    else:
        console.print(f"[yellow]未找到可重置的数据库文件。[/yellow]")

def reset_config():
    """Deletes the configuration file."""
    if os.path.exists(CONFIG_FILE):
        console.print(f"正在删除配置文件: [cyan]{CONFIG_FILE}[/cyan]...")
        os.remove(CONFIG_FILE)
        console.print("[bold green]配置文件已删除。[/bold green]")
    else:
        console.print(f"[yellow]未找到可删除的配置文件。[/yellow]") 