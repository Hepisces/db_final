import requests

def check_sql_query(user_query: str, schema: str = "") -> str:
    """
    Sends a SQL query to an external API for checking and suggestions.
    """
    headers = {
        "Authorization": "Bearer " + "pat_joz9SOnIZK1N2ohzSZciU2sO56uU5qCKuA92LSBVWvRBJpUuuHihGJxDoaVmfvpi",
        "Content-Type": "application/json"
    }

    # The user prompt is adapted to guide the API for SQL checking
    prompt = f"请检查以下SQL查询语句的正确性。如果查询语句有错误，请给出错误的原因，并提供修改建议。查询语句是：\n\n`{user_query}`"

    payload = {
        "bot_id": "7509387207439138851",
        "user": "student_123",
        "query": prompt,
        "stream": False,
        "db_info": schema
    }

    try:
        response = requests.post("https://api.coze.cn/open_api/v2/chat", headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        
        # Extract and return the actual answer content
        messages = response_data.get('messages', [])
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("type") == "answer":
                return msg.get("content", "No content in answer message.")
        
        for msg in messages:
            if msg.get("role") == "assistant":
                return msg.get("content", "No content in assistant message.")
                
        return "No valid response from API."
    except requests.exceptions.RequestException as e:
        return f"API request failed: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}" 