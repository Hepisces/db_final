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

# 全局缓存，避免重复加载模型
_model_cache = {}

def _load_model_and_tokenizer(model_path: str):
    """
    从指定路径加载模型和分词器。
    """
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype=torch.float16,
            device_map="auto",
            use_cache=True,
        )
        return tokenizer, model
    except Exception as e:
        console.print(f"[bold red]加载模型 '{model_path}' 失败: {e}[/bold red]")
        raise

def _get_cached_model(model_path: str):
    """
    获取缓存的模型，如果不在缓存中则加载。
    """
    if not model_path or not os.path.exists(model_path):
        raise FileNotFoundError(f"在路径 '{model_path}' 未找到模型。")

    if model_path not in _model_cache:
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