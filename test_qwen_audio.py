#!/usr/bin/env python3
"""测试Qwen3-VL模型是否支持音频输入"""

import base64
import requests

# 读取音频文件
audio_path = "/Users/shijingjing/Desktop/GuomaiProject/e-employee/hr-bot/data/综合办（董办）副主任岗位电话面试录音/03月20日_2（董享前）.aac"

with open(audio_path, 'rb') as f:
    audio_bytes = f.read()
audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

print(f"音频文件大小: {len(audio_bytes)} bytes")
print(f"Base64长度: {len(audio_base64)} characters")

# 测试1: 使用 audio_url 格式
url = "http://180.97.200.118:30073/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer StSrvToken-20251121-7e6c8f1b97aa4c3k"
}

payload1 = {
    "model": "Qwen3-VL-30B-A3B-Instruct",
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "请将这段音频转换为文本"
                },
                {
                    "type": "audio_url",
                    "audio_url": {
                        "url": f"data:audio/aac;base64,{audio_base64[:1000]}..."  # 只传前1000字符测试
                    }
                }
            ]
        }
    ],
    "temperature": 0.1,
    "stream": False
}

print("\n测试1: 使用 audio_url 格式")
print("-" * 50)
try:
    response = requests.post(url, headers=headers, json=payload1, timeout=30)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text[:500]}")
except Exception as e:
    print(f"错误: {e}")

# 测试2: 使用 image_url 格式（某些模型通过这种方式支持视频/音频）
payload2 = {
    "model": "Qwen3-VL-30B-A3B-Instruct",
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "请将这段音频转换为文本"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:audio/aac;base64,{audio_base64[:1000]}..."
                    }
                }
            ]
        }
    ],
    "temperature": 0.1,
    "stream": False
}

print("\n测试2: 使用 image_url 格式")
print("-" * 50)
try:
    response = requests.post(url, headers=headers, json=payload2, timeout=30)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text[:500]}")
except Exception as e:
    print(f"错误: {e}")

# 测试3: 纯文本测试（确认API正常工作）
payload3 = {
    "model": "Qwen3-VL-30B-A3B-Instruct",
    "messages": [
        {
            "role": "user",
            "content": "你好，请介绍一下你自己"
        }
    ],
    "temperature": 0.1,
    "stream": False
}

print("\n测试3: 纯文本测试")
print("-" * 50)
try:
    response = requests.post(url, headers=headers, json=payload3, timeout=30)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"响应: {content[:200]}")
    else:
        print(f"响应: {response.text[:500]}")
except Exception as e:
    print(f"错误: {e}")
