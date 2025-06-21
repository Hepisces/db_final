import sqlite3
import os
from contextlib import closing
from rich.console import Console
from rich.progress import track
from datetime import datetime
import json

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
        console.print(f"Data source configuration saved to [cyan]{CONFIG_FILE}[/cyan].")
    except Exception as e:
        console.print(f"[bold red]Failed to save configuration: {e}[/bold red]")

def load_config() -> dict:
    """Loads configuration data from a JSON file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        console.print(f"[bold red]Failed to load or parse configuration file {CONFIG_FILE}: {e}[/bold red]")
        return {}

# --- Database and Data Loading Logic ---

def create_connection():
    """Create a database connection to the SQLite database."""
    return sqlite3.connect(DB_FILE)

def create_tables(conn, data_dir: str):
    """Create tables based on the DDL.sql file from the specified directory."""
    ddl_file_path = os.path.join(data_dir, "DDL.sql")

    # Requirement: Check if DDL.sql exists before proceeding.
    if not os.path.isfile(ddl_file_path):
        console.print(f"[bold red]Error: DDL file not found at '{ddl_file_path}'.[/bold red]")
        console.print("Please ensure a 'DDL.sql' file exists in the specified data directory.")
        raise FileNotFoundError(f"DDL.sql not found in {data_dir}")

    console.print(f"Reading table schema from [cyan]{ddl_file_path}[/cyan]...")
    try:
        with open(ddl_file_path, 'r', encoding='utf-8') as f:
            ddl_script = f.read()
        with closing(conn.cursor()) as cursor:
            cursor.executescript(ddl_script)
        conn.commit()
        console.print("[green]Tables created successfully.[/green]")
    except Exception as e:
        console.print(f"[bold red]An error occurred while creating tables: {e}[/bold red]")
        raise

def import_real_data(conn, data_dir: str):
    """Import data from the .sql files found in the specified directory."""
    cursor = conn.cursor()
    
    # Order matters due to foreign keys
    sql_files = ['customer.sql', 'devlist.sql', 'control.sql', 'devupdata.sql']
    
    console.print(f"[yellow]Starting data import from [bold]{data_dir}[/bold]...[/yellow]")
    
    for file_name in sql_files:
        file_path = os.path.join(data_dir, file_name)
        if not os.path.exists(file_path):
            console.print(f"[yellow]Warning: Data file [cyan]{file_name}[/cyan] not found in '{data_dir}'. Skipping.[/yellow]")
            continue
        
        console.print(f"Processing [cyan]{file_path}[/cyan]...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in track(f, description=f"Importing {file_name}..."):
                    sql_statement = line.strip()
                    if sql_statement:
                        sql_statement = sql_statement.replace("INSERT INTO public.", "INSERT INTO ")
                        cursor.execute(sql_statement)
            conn.commit()
            console.print(f"[green]Successfully imported {file_name}.[/green]")
        except Exception as e:
            console.print(f"[bold red]An error occurred while importing {file_name}: {e}[/bold red]")
            # Continue with the next file
            
    console.print("[bold green]All available data has been successfully imported![/bold green]")

def db_exists():
    """Check if the database file exists and is not empty."""
    if not os.path.exists(DB_FILE):
        return False
    # Further check if tables are populated
    try:
        with create_connection() as conn:
            cursor = conn.cursor()
            # This will fail if no tables exist, which is the desired behavior.
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
            return cursor.fetchone() is not None
    except sqlite3.Error:
        return False

def reset_db():
    """
    Deletes the existing database file, allowing for a clean import.
    """
    if os.path.exists(DB_FILE):
        console.print(f"Deleting existing database file: [cyan]{DB_FILE}[/cyan]...")
        os.remove(DB_FILE)
        console.print("[bold green]Database has been reset.[/bold green]")
    else:
        console.print(f"[yellow]No database file found to reset.[/yellow]") 