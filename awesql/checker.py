import requests
from rich.console import Console
import json
console = Console()

def check_sql_query(user_query: str, schema: str = "") -> str:
    """
    Sends a SQL query to an external API for checking and suggestions.
    """
    if not schema:
        return "DDL schema not provided. Cannot check query without it."

    try:
        response = requests.post(
            "https://api.coze.cn/v1/workflow/run",
            headers={
                "Authorization": "Bearer pat_joz9SOnIZK1N2ohzSZciU2sO56uU5qCKuA92LSBVWvRBJpUuuHihGJxDoaVmfvpi",
                "Content-Type": "application/json",
            },
            json={
                "workflow_id": "7509391259422605350",
                "parameters": {
                    "input_sql": user_query,
                    "db_info": schema,
                }
            }
        )
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        
        data = response.json()
        
        # Check if the response indicates success and contains the expected message structure
        if data.get("code") == 0 and data.get("msg") == "Success":
            inner_data_str = data.get('data')
            if not inner_data_str:
                return "API响应成功，但未包含有效的'data'内容。"
            
            inner_data = json.loads(inner_data_str)
            return inner_data.get('data', "未能从内部数据结构中提取检查结果。")

        # If the structure is not as expected, return a generic error with the raw data
        return f"未能从API获取有效检查结果。响应: {data}"

    except requests.exceptions.HTTPError as http_err:
        return f"HTTP错误: {http_err} - {response.text}"
    except requests.exceptions.RequestException as req_err:
        return f"请求错误: {req_err}"
    except Exception as e:
        return f"处理检查请求时发生未知错误: {e}" 