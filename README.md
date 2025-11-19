# NetMind API 转发服务 🚀

这是一个 **FastAPI 微服务**，用于代理 OpenAI 兼容的 `/v1/chat/completions` 请求到 NetMind API。

## ✨ 主要功能

- ✅ **完全兼容** OpenAI API 格式
- ✅ **支持流式和非流式**响应
- ✅ **自动插入自定义广告**（在AI回复末尾）
- ✅ **API密钥池轮询**（多个密钥自动切换）
- ✅ **智能重试机制**（401/429错误自动换Key重试）
- ✅ **访问令牌认证**（保护你的服务）
- ✅ **已通过单元测试**（所有核心功能均已验证）

## 🎯 测试结果

代码已通过完整的单元测试，验证了以下功能：

| 测试项 | 状态 | 说明 |
|--------|------|------|
| Token认证 | ✅ 通过 | 无效token被正确拒绝 |
| 非流式响应 | ✅ 通过 | 广告正确追加到回复末尾 |
| 流式响应 | ✅ 通过 | 广告在[DONE]之前插入 |
| 密钥轮询 | ✅ 通过 | 401错误时自动切换下一个密钥 |

**测试命令：**
```bash
python -m unittest discover tests
```

## 🚀 快速开始

### 1. 配置服务

编辑 `main.py`，修改以下关键配置：

```python
# 1. NetMind API 密钥池（填入你的真实密钥）
NETMIND_KEY_POOL = [
    "your-real-netmind-key-1",  # ← 替换成真实密钥
    "your-real-netmind-key-2",  # 可以添加多个
    "your-real-netmind-key-3",
]

# 2. 自定义访问令牌（客户端需要用这个密钥访问你的服务）
MY_ACCESS_TOKEN = "sk-mydomain-vip-key"  # ← 改成你自己的

# 3. 广告内容（会自动添加到AI回复末尾）
AD_SUFFIX = "\n\n(✨ 本回复由 [你的名字] 的超级服务器提供，算力支持: NetMind ✨)"
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动服务

```bash
# 方式1：直接运行
python main.py

# 方式2：使用uvicorn（推荐）
uvicorn main:app --host 0.0.0.0 --port 8000

# 方式3：后台运行
nohup python main.py > server.log 2>&1 &
```

服务将在 `http://0.0.0.0:8000` 启动。

## 📝 客户端使用示例

### Python (OpenAI SDK)

```python
import openai

# 配置客户端指向你的服务
client = openai.OpenAI(
    api_key="sk-mydomain-vip-key",  # 你设置的 MY_ACCESS_TOKEN
    base_url="http://your-server:8000/v1"
)

# 非流式请求
response = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "你好"}],
    stream=False
)
print(response.choices[0].message.content)
# 输出会包含广告后缀

# 流式请求
stream = client.chat.completions.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "你好"}],
    stream=True
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
# 最后会输出广告内容
```

### cURL

```bash
# 测试非流式
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-mydomain-vip-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'

# 测试流式
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer sk-mydomain-vip-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }' \
  --no-buffer
```

### JavaScript/TypeScript

```javascript
const response = await fetch('http://your-server:8000/v1/chat/completions', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer sk-mydomain-vip-key',
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    model: 'gpt-3.5-turbo',
    messages: [{role: 'user', content: '你好'}],
    stream: false
  })
});

const data = await response.json();
console.log(data.choices[0].message.content);
// 包含广告后缀
```

## 🔍 广告功能验证

### 非流式响应
广告会自动**追加**到 AI 回复的末尾：
```json
{
  "choices": [{
    "message": {
      "content": "AI的回复内容\n\n(✨ 本回复由 xxx 提供，算力支持: NetMind ✨)"
    }
  }]
}
```

### 流式响应
广告会在 `[DONE]` 信号之前，作为独立的数据块发送：
```
data: {"choices": [{"delta": {"content": "AI"}}]}

data: {"choices": [{"delta": {"content": "的回复"}}]}

data: {"choices": [{"delta": {"content": "\n\n(✨ 广告内容 ✨)"}}]}

data: [DONE]
```

## 🎯 API端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/chat/completions` | POST | OpenAI兼容的主端点 |
| `/chat/completions` | POST | 备用端点（不带/v1前缀） |
| `/docs` | GET | FastAPI自动生成的API文档 |

## 🔧 故障排查

### 问题1：上游返回401错误

**原因：** NetMind API密钥无效或已过期

**解决：**
1. 检查 `NETMIND_KEY_POOL` 中的密钥是否正确
2. 到 [NetMind官网](https://api.netmind.ai) 获取有效密钥
3. 确认密钥配额未用完

**特性：** 服务会自动切换到下一个密钥重试

### 问题2：广告未显示

**检查方法：**
```python
# 确认 AD_SUFFIX 变量设置正确
print(main.AD_SUFFIX)

# 流式响应：检查服务器日志，确认广告数据块发送
# 非流式响应：检查返回的 content 是否包含 AD_SUFFIX
```

### 问题3：客户端提示认证失败

**原因：** 客户端使用的token与 `MY_ACCESS_TOKEN` 不匹配

**解决：**
```python
# 确保客户端使用正确的token
client = openai.OpenAI(
    api_key="sk-mydomain-vip-key",  # 必须与main.py中的MY_ACCESS_TOKEN一致
    base_url="http://your-server:8000/v1"
)
```

## 🏭 生产环境部署建议

### 1. 使用环境变量（安全）

```python
import os

MY_ACCESS_TOKEN = os.getenv("MY_ACCESS_TOKEN", "default-key")
NETMIND_KEY_POOL = os.getenv("NETMIND_KEYS", "").split(",")
```

### 2. 使用Nginx反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # 流式响应支持
        proxy_buffering off;
        proxy_cache off;
    }
}
```

### 3. 使用systemd管理服务

创建 `/etc/systemd/system/api-proxy.service`:

```ini
[Unit]
Description=NetMind API Proxy Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动：
```bash
sudo systemctl start api-proxy
sudo systemctl enable api-proxy
```

### 4. 启用HTTPS

```bash
# 使用 Let's Encrypt
certbot --nginx -d your-domain.com
```

## 📊 服务监控

添加日志记录：

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api_proxy.log'),
        logging.StreamHandler()
    ]
)
```

## 💡 常见问题

**Q: 服务能正常转发聊天吗？**  
A: ✅ 是的！已通过单元测试验证，完全兼容OpenAI API格式。

**Q: 广告会影响AI回复质量吗？**  
A: ❌ 不会。广告只是追加在末尾，不影响AI生成的核心内容。

**Q: 可以自定义广告样式吗？**  
A: ✅ 可以。修改 `AD_SUFFIX` 变量，支持换行和特殊字符。

**Q: 密钥池如何工作？**  
A: 🔄 轮流使用，遇到401/429错误自动切换下一个密钥。

**Q: 支持哪些模型？**  
A: 🎯 支持所有NetMind支持的模型，客户端指定什么就转发什么。

**Q: 可以部署在VPS上吗？**  
A: ✅ 完全可以！适合部署在任何Linux VPS上。

## 🔒 安全建议

1. ✅ 使用环境变量存储密钥（不要硬编码）
2. ✅ 启用HTTPS（保护密钥传输）
3. ✅ 定期轮换密钥
4. ✅ 添加IP白名单（可选）
5. ✅ 启用访问日志审计

## 📚 依赖

- `fastapi` >= 0.103.0 - Web框架
- `httpx` >= 0.24.0 - HTTP客户端
- `uvicorn` >= 0.23.0 - ASGI服务器

## 🎉 结论

✅ **服务已测试完成，可以正常部署使用！**

- 认证功能正常
- 流式/非流式响应正常
- 广告插入功能正常
- 密钥轮询功能正常

只需要：
1. 填入真实的 NetMind API 密钥
2. 设置你的自定义访问令牌
3. 自定义广告内容
4. 启动服务即可！

---

**维护者：** Engine AI  
**最后更新：** 2024
