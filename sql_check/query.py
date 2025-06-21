import requests
import sys

def send_coze_query(user_query: str):
    headers = {
        "Authorization": "Bearer " + "pat_joz9SOnIZK1N2ohzSZciU2sO56uU5qCKuA92LSBVWvRBJpUuuHihGJxDoaVmfvpi",
        "Content-Type": "application/json"
    }

    payload = {
        "bot_id": "7509387207439138851",
        "user": "student_123",
        "query": user_query,
        "stream": False
    }

    try:
        response = requests.post("https://api.coze.cn/open_api/v2/chat", headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        
        # 提取并返回实际答案内容
        messages = response_data.get('messages', [])
        for msg in messages:
            # 专门寻找type为"answer"的消息，这是真正的回答内容
            if msg.get("role") == "assistant" and msg.get("type") == "answer":
                return msg.get("content", "无内容")
        
        # 如果没找到answer类型，返回第一个assistant消息
        for msg in messages:
            if msg.get("role") == "assistant":
                return msg.get("content", "无内容")
                
        return "无有效回复"
    except Exception as e:
        print("请求失败：", str(e))
        return "生成失败，请稍后重试。"

def main():
    print("=== Coze 机器人自然语言查询终端 ===")
    print("输入 'exit', 'quit' 或 'q' 退出程序")
    print("输入你的问题开始对话...")
    
    while True:
        # 获取用户输入
        user_input = input("\n你: ")
        
        # 检查是否退出
        if user_input.lower() in ['exit', 'quit', 'q']:
            print("再见！")
            sys.exit(0)
        
        # 空输入处理
        if not user_input.strip():
            continue
            
        # 发送查询并获取回答
        print("\n正在思考...")
        answer = send_coze_query(user_input)
        
        # 打印回答
        print("\nCoze: " + answer)

if __name__ == "__main__":
    main()
