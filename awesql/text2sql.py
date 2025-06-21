from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import os
import warnings
from rich.console import Console

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
    Loads the SQLCoder model and tokenizer from a local path.
    Caches the model and tokenizer globally to avoid reloading on subsequent calls.
    """
    if _model_cache["model"] and _model_cache["tokenizer"]:
        console.print("[green]Model already loaded from cache.[/green]")
        return _model_cache["tokenizer"], _model_cache["model"]

    console.print("[yellow]Loading SQLCoder model... (This might take a moment on first run)[/yellow]")
    
    try:
        # Correctly construct the path for cross-platform compatibility
        model_path = os.path.join("text2sql", "models--defog--sqlcoder-7b-2", "snapshots", "7e5b6f7981c0aa7d143f6bec6fa26625bdfcbe66")
        
        if not os.path.isdir(model_path):
            console.print(f"[bold red]Error: Model directory not found at '{os.path.abspath(model_path)}'[/bold red]")
            console.print("Please make sure the SQLCoder model is downloaded and placed in the project root.")
            return None, None

        console.print(f"Loading model from local path: [cyan]{model_path}[/cyan]")
        
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
            local_files_only=True
        )
        
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
        
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            trust_remote_code=True,
            device_map="auto",
            local_files_only=True,
            use_flash_attention_2=False,
            low_cpu_mem_usage=True
        )
        
        model.config.pad_token_id = tokenizer.pad_token_id
        model.eval()
        
        # Cache the model and tokenizer
        _model_cache["tokenizer"] = tokenizer
        _model_cache["model"] = model
        
        console.print("[bold green]✅ Model loaded successfully![/bold green]")
        return tokenizer, model
        
    except Exception as e:
        console.print(f"[bold red]❌ Model loading failed: {e}[/bold red]")
        return None, None

def generate_sql(question: str, schema: str = "") -> str:
    """
    Generates SQL from a natural language question using the loaded SQLCoder model.
    """
    tokenizer, model = load_model()
    
    if not tokenizer or not model:
        return "Model not loaded correctly. Cannot generate SQL."
    
    prompt = f"### Task\nGenerate a SQL query to answer this question: {question}\n\n"
    if schema:
        prompt += f"### Database Schema\n{schema}\n\n"
    prompt += "### SQL\n"
    
    try:
        inputs = tokenizer(
            prompt,
            return_tensors="pt",
            return_attention_mask=True
        )
        
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
        
        full_response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract only the generated SQL part
        sql_part = full_response.split("### SQL")[-1].strip()
        return sql_part
        
    except Exception as e:
        console.print(f"[bold red]An error occurred during SQL generation: {e}[/bold red]")
        return "Failed to generate SQL." 