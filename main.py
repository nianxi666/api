import os
import json
import httpx
import asyncio
import time
from typing import List
from itertools import cycle
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

# ==================== 核心配置区 ====================

# 1. 上游配置
UPSTREAM_URL = "https://api.netmind.ai/inference-api/openai/v1/chat/completions"

# 2. 密钥池 (自动轮询，自动重试)
# 填入你所有的 NetMind 真实 Key
NETMIND_KEY_POOL = [
    "53edd1de80974744bc5007436e17da04", # Key 1
    "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxx", # Key 2
    "sk-yyyyyyyyyyyyyyyyyyyyyyyyyyyyy", # Key 3
]

# 3. 你的自定义 Key (只有用这个 Key 才能调你的接口)
MY_ACCESS_TOKEN = "sk-mydomain-vip-key"

# 4. 广告配置 (支持换行)
AD_SUFFIX = "\n\n(✨ 本回复由 [你的名字] 的超级服务器提供，算力支持: NetMind ✨)"

# ===================================================

app = FastAPI()

# 创建一个循环迭代器，用于轮询 Key
key_iterator = cycle(NETMIND_KEY_POOL)

def get_next_key():
    """获取下一个 Key"""
    return next(key_iterator)

async def verify_token(request: Request):
    """验证用户的 Key"""
    auth = request.headers.get("Authorization")
    if not auth or auth.replace("Bearer ", "") != MY_ACCESS_TOKEN:
        raise HTTPException(status_code=401, detail="无效的 API Key，请联系管理员充值。")

async def inject_ad_to_stream(upstream_response):
    """
    流式响应处理生成器：
    1. 转发原始流
    2. 在结束前，伪造数据包插入广告
    3. 发送结束信号
    """
    async for chunk in upstream_response.aiter_lines():
        if not chunk:
            continue
        
        # 去掉 data: 前缀处理 JSON
        line = chunk.decode("utf-8").strip()
        if line.startswith("data: "):
            data_str = line[6:]
            
            # 如果上游发来结束信号，先别急着发给用户
            if data_str == "[DONE]":
                # --- 开始植入广告 ---
                # 构造一个符合 OpenAI 格式的 Delta 数据包
                ad_packet = {
                    "choices": [{
                        "index": 0,
                        "delta": {"content": AD_SUFFIX}, # 这里插入广告
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(ad_packet)}\n\n".encode("utf-8")
                
                # 发送真正的结束信号
                yield b"data: [DONE]\n\n"
                break
            
            # 正常转发内容
            yield chunk + b"\n"
        else:
            # 保持心跳或其他非 data 行
            yield chunk + b"\n"

@app.post("/v1/chat/completions")
@app.post("/chat/completions")
async def proxy_chat(request: Request):
    await verify_token(request)
    
    body = await request.json()
    is_stream = body.get("stream", False)
    
    # 最大重试次数 = Key 的数量
    max_retries = len(NETMIND_KEY_POOL)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(max_retries):
            current_key = get_next_key()
            
            headers = {
                "Authorization": f"Bearer {current_key}",
                "Content-Type": "application/json"
            }
            
            try:
                # 发起请求
                req = client.build_request("POST", UPSTREAM_URL, headers=headers, json=body)
                response = await client.send(req, stream=True)
                
                # 如果状态码是 401 (未授权/Key失效) 或 429 (超额/并发限制)
                if response.status_code in [401, 429]:
                    print(f"⚠️ Key {current_key[:8]}... 失效或超额，正在切换下一个 Key 重试...")
                    await response.aclose()
                    continue # 进入下一次循环，换 Key
                
                # 如果成功连接 (200 OK)
                if response.status_code == 200:
                    
                    # 情况 A: 流式响应 (最常见)
                    if is_stream:
                        return StreamingResponse(
                            inject_ad_to_stream(response),
                            media_type="text/event-stream"
                        )
                    
                    # 情况 B: 非流式响应 (一次性返回)
                    else:
                        data = await response.read()
                        await response.aclose()
                        response_json = json.loads(data)
                        
                        # 修改 JSON 内容插入广告
                        try:
                            content = response_json['choices'][0]['message']['content']
                            response_json['choices'][0]['message']['content'] = content + AD_SUFFIX
                        except:
                            pass # 如果解析失败就不加广告了，保证不报错
                            
                        return JSONResponse(content=response_json)
                
                # 其他错误 (500 等)，直接返回报错，不重试
                return JSONResponse(
                    status_code=response.status_code,
                    content=json.loads(await response.read())
                )

            except Exception as e:
                print(f"网络错误: {e}")
                # 网络错误也可以选择重试，或者直接报错
                if attempt == max_retries - 1:
                    raise HTTPException(status_code=500, detail="所有 Key 均尝试失败或上游服务不可用")

    raise HTTPException(status_code=500, detail="密钥池耗尽，无法处理请求")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
