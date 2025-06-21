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

# --- Configuration ---
CONFIG_FILE = "awesql_config.json"
DEFAULT_DB_NAME = "project2025.db"

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

def create_connection(db_name: str = DEFAULT_DB_NAME):
    """Create a database connection to the SQLite database specified by db_name."""
    try:
        conn = sqlite3.connect(db_name)
        return conn
    except sqlite3.Error as e:
        console.print(e)
    return None

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

def db_exists(db_name: str = DEFAULT_DB_NAME) -> bool:
    """Check if the database file exists and is not empty."""
    if not os.path.exists(db_name) or os.path.getsize(db_name) == 0:
        return False
    try:
        with create_connection(db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
            if cursor.fetchone() is None:
                return False
        return True
    except sqlite3.Error:
        return False

def execute_query(query: str, db_name: str = DEFAULT_DB_NAME):
    """
    Execute a query and its EXPLAIN QUERY PLAN against the specified database.
    Returns (result_df, plan_df) on success, or (None, None) on error.
    """
    try:
        with create_connection(db_name) as conn:
            plan_df = pd.read_sql_query(f"EXPLAIN QUERY PLAN {query}", conn)
            result_df = pd.read_sql_query(query, conn)
            return result_df, plan_df
    except sqlite3.Error as e:
        console.print(f"[bold red]数据库错误: {e}[/bold red]")
        return None, None
    except Exception as e:
        console.print(f"[bold red]发生未知错误: {e}[/bold red]")
        return None, None

def reset_db(db_name: str = DEFAULT_DB_NAME):
    """
    Deletes the existing database file, allowing for a clean import.
    """
    if os.path.exists(db_name):
        console.print(f"正在删除现有数据库文件: [cyan]{db_name}[/cyan]...")
        os.remove(db_name)
        console.print("[bold green]数据库已重置。[/bold green]")
    else:
        console.print(f"[yellow]未找到可重置的数据库文件 '{db_name}'。[/yellow]")

def reset_config():
    """Deletes the configuration file."""
    if os.path.exists(CONFIG_FILE):
        console.print(f"正在删除配置文件: [cyan]{CONFIG_FILE}[/cyan]...")
        os.remove(CONFIG_FILE)
        console.print("[bold green]配置文件已删除。[/bold green]")
    else:
        console.print(f"[yellow]未找到可删除的配置文件。[/yellow]")

def get_table_names(db_name: str = DEFAULT_DB_NAME) -> list[str] | None:
    """
    Retrieves a list of all table names from the database.
    """
    try:
        with create_connection(db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in cursor.fetchall()]
            return tables
    except sqlite3.Error as e:
        console.print(f"[bold red]数据库错误: 无法获取表列表: {e}[/bold red]")
        return None 