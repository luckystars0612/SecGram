import requests
from config.settings import CHATGPT_API_KEY
from message_broker import send_to_bot_service

def call_chatgpt(prompt):
    response = requests.post(
        "https://api.openai.com/v1/completions",
        headers={"Authorization": f"Bearer {CHATGPT_API_KEY}"},
        json={"prompt": prompt, "max_tokens": 100}
    )
    data = {"source": "ChatGPT", "content": response.json()["choices"][0]["text"]}
    send_to_bot_service(data)

if __name__ == "__main__":
    call_chatgpt("Summarize this text")