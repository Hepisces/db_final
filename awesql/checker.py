import requests

def check_sql_query(user_query: str, schema: str = "") -> str:
    """
    Sends a SQL query to an external API for checking and suggestions.
    """
    if not schema:
        return "DDL schema not provided. Cannot check query without it."

    try:
        console.print("正在检查SQL语法...")
        response = requests.post(
            "https://api.coze.com/open_api/v2/chat",
            headers={
                "Authorization": "Bearer " + "pat_joz9SOnIZK1N2ohzSZciU2sO56uU5qCKuA92LSBVWvRBJpUuuHihGJxDoaVmfvpi",
                "Content-Type": "application/json",
            },
            json={
                "conversation_id": "123",
                "bot_id": "7369931785568550920",
                "user": "12345678",
                "query": f"你是一个SQL检查工具，我会给你一个DDL文件，然后给你一个查询请求，你帮我检查一下这个查询请求有没有问题，如果有问题，请给我修改建议，如果没有问题，就直接告诉我没有问题即可。不要输出任何与结果无关的内容。DDL文件如下：{schema}, 查询请求如下：{user_query}",
                "stream": False,
            },
            timeout=60  # Set a timeout for the request
        )
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        
        data = response.json()
        
        # Check if the response indicates success and contains the expected message structure
        if data.get("code") == 0 and data.get("msg") == "success":
            for message in data.get("messages", []):
                if message.get("type") == "answer":
                    content = message.get("content", "").strip()
                    if "没有问题" in content:
                        return "SQL查询未发现问题。"
                    return f"建议: {content}"

        # If the structure is not as expected, return a generic error with the raw data
        return f"未能从API获取有效检查结果。响应: {data}"

    except requests.exceptions.HTTPError as http_err:
        return f"HTTP错误: {http_err} - {response.text}"
    except requests.exceptions.RequestException as req_err:
        return f"请求错误: {req_err}"
    except Exception as e:
        return f"处理检查请求时发生未知错误: {e}" 