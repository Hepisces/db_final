from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import os
import warnings
from rich.console import Console
import time

# Import db module to access config functions
from . import db

console = Console()

# Ignore specific warnings from transformers
warnings.filterwarnings("ignore", message=".*Torch was not compiled with flash attention.*")

# Global cache for the model and tokenizer to avoid reloading
_model_cache = {
    "tokenizer": None,
    "model": None
}

def load_model():
    """
    Loads the SQLCoder model and tokenizer from a local path specified in the config,
    with a fallback to a default path. Caches the model to avoid reloading.
    """
    if _model_cache["model"] and _model_cache["tokenizer"]:
        console.print("[green]Model already loaded from cache.[/green]")
        return _model_cache["tokenizer"], _model_cache["model"]

    console.print("[yellow]Loading SQLCoder model... (This might take a moment on first run)[/yellow]")
    
    config = db.load_config()
    model_path = config.get('model_path')
    using_default_path = False

    if not model_path:
        using_default_path = True
        default_path_str = os.path.join("text2sql", "models--defog--sqlcoder-7b-2", "snapshots", "7e5b6f7981c0aa7d143f6bec6fa26625bdfcbe66")
        console.print(f"[yellow]Warning: Model path not configured. Falling back to default path:[/yellow]")
        console.print(f"  [dim]{default_path_str}[/dim]")
        console.print(f"  [yellow]You can set a custom path with 'awesql config set-model-path'.[/yellow]")
        model_path = default_path_str

    if not model_path or not os.path.exists(model_path):
        raise FileNotFoundError(f"在路径 '{model_path}' 未找到模型。")

    if not _model_cache.get(model_path):
        console.print("[yellow]正在加载模型...这可能需要一些时间。[/yellow]")
        _model_cache[model_path] = _load_model_and_tokenizer(model_path)
        console.print("[green]模型已加载并缓存。[/green]")
    else:
        console.print("[green]正在使用缓存的模型。[/green]")
        
    return _model_cache[model_path]

def generate_sql(question: str, ddl_path: str, model_path: str) -> str:
    """
    Generates SQL from a natural language question using the loaded SQLCoder model.
    """
    try:
        with open(ddl_path, 'r', encoding='utf-8') as f:
            ddl = f.read()
    except FileNotFoundError:
        return f"错误：DDL 文件 '{ddl_path}' 未找到。"

    try:
        tokenizer, model = _get_cached_model(model_path)
    except FileNotFoundError as e:
        return str(e)

    prompt = f"""### Instructions:
Your task is to convert a question into a SQL query, given a database schema.
Adhere to these rules:
- **Deliberately go through the question and database schema word by word** to appropriately answer the question.
- **Use Table Aliases** to prevent ambiguity. For example, `SELECT table1.col1, table2.col2 FROM table1 JOIN table2 ON table1.id = table2.id`.
- When creating a ratio, always cast the numerator as `REAL` or `FLOAT` to ensure precision.

### Input:
Generate a SQL query that answers the following question:
`{question}`

### Database Schema:
This is the schema of the database:
```sql
{ddl}
```

### Response:
```sql
"""
    console.print("正在生成SQL查询...")
    try:
        start_time = time.time()
        
        inputs = tokenizer(prompt, return_tensors="pt")
        
        device = next(model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=200,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
                num_beams=5,
                num_return_sequences=1
            )
        
        generated_sql = tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Clean up the output to only get the SQL
        if "```sql" in generated_sql:
            generated_sql = generated_sql.split("```sql")[1]
        if "```" in generated_sql:
            generated_sql = generated_sql.split("```")[0]
        
        generated_sql = generated_sql.strip()

        end_time = time.time()
        console.print(f"[green]在 {end_time - start_time:.2f} 秒内生成SQL。[/green]")
        return generated_sql

    except Exception as e:
        console.print(f"[bold red]生成SQL失败: {e}[/bold red]")
        return "" 