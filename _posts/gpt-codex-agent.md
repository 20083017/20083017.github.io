---
layout:     post
title:      Codex / Copilot Agent 使用记录
subtitle:   Homebrew 国内源、Copilot 模型切换报错与一份 Codex Agent Stage 2 脚手架
date:       2026-04-25
author:     BY
header-img: img/post-bg-ios9-web.jpg
catalog: true
tags:
    - Agent
    - Copilot
    - Codex
    - OpenAI
---

>原始笔记把 Homebrew 安装、Copilot 模型切换报错和一段 Codex Agent 脚手架混在一起，这里按「环境准备 / 使用问题 / 配置 / 脚手架」分节整理。

## 1. Homebrew 国内安装入口

国内网络下，官方 Homebrew 安装脚本经常拉不下来，可以用 gitee 镜像做替代：

```bash
/bin/bash -c "$(curl -fsSL https://gitee.com/cunkai/HomebrewCN/raw/master/Homebrew.sh)"
```

这是一份社区维护的镜像脚本，仅推荐用于个人开发机；公司机器或生产环境优先用官方源或公司内部源。

## 2. Agent 会话使用中常见疑问

原始笔记里只留了几个关键词，这里整理成提醒自己回看时要确认的问题清单：

- 会话上下文压缩 / 清理策略：是否会丢失关键历史？
- 上下文累积带来的 token 消耗：什么时候手动清理一次更合适？
- 模型切换是否会让 Agent「忘掉」前面的对话？
- 长任务下，要不要把关键状态写进 memory，而不是只靠对话历史？

这些都不是某一个工具的具体配置项，而是用 Agent 时长期需要回头复盘的问题。

## 3. Copilot 模型切换的一个真实报错

从一个模型切到另一个模型时，遇到过：

```text
Sorry, your request failed. Please try again. Request id: 189fc83e-5b0a-49b4-937d-4ec3011c22f7

Reason: Request Failed: 400 {"error":{"message":"Unsupported parameter: 'top_p' is not supported with this model.","code":"invalid_request_body"}}
```

原始笔记里的应对结论是：**卸载 Copilot 后重新安装一次，再切回目标模型，就不会再出这个错。**

可以理解为：客户端缓存了一组对前一个模型还能用、但对当前模型不再支持的请求参数（这里是 `top_p`），重装后请求模板被重置，问题随之消失。

后续遇到类似 `Unsupported parameter` 报错时，先按这个思路怀疑客户端缓存，而不是直接去改服务端模型。

## 4. OpenClaw 配置入口

如果用到 OpenClaw 之类的本地 Agent / Gateway 工具，配置文件目录是：

```text
~/.openclaw/openclaw.json
```

常用命令：

```bash
# 重启 gateway
openclaw gateway restart

# 打开 dashboard
openclaw dashboard

# 修改配置
openclaw configure
```

启动样例输出：

```text
🦞 OpenClaw 2026.4.10 (44e5b62)
   I run on caffeine, JSON5, and the audacity of "it worked on my machine."

Restarted systemd service: openclaw-gateway.service
```

## 5. Codex Agent Stage 2 最小脚手架

原始笔记里保留了一份 shell 脚本，用来一次性拉起 Codex Agent 第二阶段所需的目录、依赖和服务。这里按结构分块整理，方便回看。

### 5.1 目录与依赖

```bash
#!/usr/bin/env bash
set -e

echo "🚀 初始化 Codex Agent (Stage 2)..."

mkdir -p codex-agent/{memory,context,tools}
cd codex-agent

cat > requirements.txt <<'EOF'
fastapi
uvicorn
openai
chromadb
python-dotenv
redis
numpy
EOF
```

### 5.2 向量记忆：`memory/vector_store.py`

```python
import chromadb

client = chromadb.Client()
collection = client.get_or_create_collection("memory")


def save_memory(text: str) -> None:
    collection.add(
        documents=[text],
        ids=[str(hash(text))],
    )


def search_memory(query: str, top_k: int = 5, threshold: float = 0.7):
    results = collection.query(
        query_texts=[query],
        n_results=top_k,
    )

    docs = results["documents"][0]
    distances = results["distances"][0]

    return [
        doc
        for doc, dist in zip(docs, distances)
        if dist < (1 - threshold)
    ]
```

### 5.3 会话存储：`memory/session.py`

```python
import json

import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)
SESSION_TTL = 3600


def get_session(session_id: str):
    data = r.get(session_id)
    if data:
        return json.loads(data)
    return []


def save_session(session_id: str, messages) -> None:
    r.setex(session_id, SESSION_TTL, json.dumps(messages))
```

### 5.4 上下文拼装：`context/builder.py`

```python
from memory.vector_store import search_memory


def build_context(user_input: str, history) -> str:
    memories = search_memory(user_input)

    history_text = "\n".join(
        f"User: {h['user']}\nAssistant: {h['assistant']}"
        for h in history[-5:]
    )

    return f"""
You are a senior engineer agent.

Conversation history:
{history_text}

Relevant memory:
{memories}

User request:
{user_input}
"""
```

### 5.5 工具注册与执行：`tools/registry.py` / `tools/executor.py`

```python
# tools/registry.py
import ast
import operator as op

# 仅允许常见算术运算符，避免 eval 带来的任意代码执行风险
_ALLOWED_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Mod: op.mod,
    ast.Pow: op.pow,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("unsupported expression")


def echo_tool(input_text: str) -> str:
    return f"Echo: {input_text}"


def calc_tool(input_text: str) -> str:
    try:
        tree = ast.parse(input_text, mode="eval")
        return str(_safe_eval(tree))
    except Exception:
        return "error"


def get_tools():
    return {
        "echo": echo_tool,
        "calc": calc_tool,
    }
```

```python
# tools/executor.py
from tools.registry import get_tools

tools = get_tools()


def execute_tool(name: str, input_text: str) -> str:
    if name in tools:
        return tools[name](input_text)
    return "Tool not found"
```

> 提醒：`calc_tool` 仅做受限的算术表达式求值（基于 `ast` 白名单），避免直接用 `eval()` 带来的任意代码执行风险。如需支持更复杂的表达式，建议引入专门的安全求值库或沙箱。

### 5.6 入口服务：`main.py`

```python
from fastapi import FastAPI
from openai import OpenAI

from context.builder import build_context
from memory.session import get_session, save_session
from memory.vector_store import save_memory
from tools.executor import execute_tool

app = FastAPI()
client = OpenAI()


@app.post("/chat")
async def chat(input: str, session_id: str = "default"):
    history = get_session(session_id)
    context = build_context(input, history)

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=context,
    )
    output = response.output[0].content[0].text

    if output.startswith("TOOL:"):
        try:
            _, tool_name, tool_input = output.split(":", 2)
            tool_result = execute_tool(tool_name, tool_input)
            output = f"Tool result: {tool_result}"
        except Exception:
            output = "Tool execution error"

    history.append({"user": input, "assistant": output})
    save_session(session_id, history)
    save_memory(f"Q: {input}\nA: {output}")

    return {"response": output}
```

### 5.7 启动顺序

```bash
echo "📦 安装依赖..."
pip install -r requirements.txt

echo "🧠 启动 Redis..."
docker run -d -p 6379:6379 redis

echo "🚀 启动服务..."
uvicorn main:app --reload
```

## 后续可补的方向

- Agent 会话压缩 / 摘要的具体策略
- memory 的检索阈值调参经验
- 工具调用从「字符串约定」升级到结构化 function call
- 多模型切换时如何隔离客户端缓存
