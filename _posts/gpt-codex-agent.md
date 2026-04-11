
#### 可能存在的问题 

安装 homebrew
```
/bin/bash -c "$(curl -fsSL https://gitee.com/cunkai/HomebrewCN/raw/master/Homebrew.sh)"
```

agent 会话 压缩？ 清理？ 消耗大量token？ 忘掉历史会话？






### 阶段2

```
#!/bin/bash

echo "🚀 初始化 Codex Agent (Stage 2)..."

# 创建目录
mkdir -p codex-agent/{memory,context,tools}
cd codex-agent

# requirements.txt
cat > requirements.txt <<EOF
fastapi
uvicorn
openai
chromadb
python-dotenv
redis
numpy
EOF

# ========================
# memory/vector_store.py
# ========================
cat > memory/vector_store.py <<EOF
import chromadb

client = chromadb.Client()
collection = client.get_or_create_collection("memory")

def save_memory(text):
    collection.add(
        documents=[text],
        ids=[str(hash(text))]
    )

def search_memory(query, top_k=5, threshold=0.7):
    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )

    docs = results["documents"][0]
    distances = results["distances"][0]

    filtered = [
        doc for doc, dist in zip(docs, distances)
        if dist < (1 - threshold)
    ]

    return filtered
EOF

# ========================
# memory/session.py
# ========================
cat > memory/session.py <<EOF
import redis
import json

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

SESSION_TTL = 3600

def get_session(session_id):
    data = r.get(session_id)
    if data:
        return json.loads(data)
    return []

def save_session(session_id, messages):
    r.setex(session_id, SESSION_TTL, json.dumps(messages))
EOF

# ========================
# context/builder.py
# ========================
cat > context/builder.py <<EOF
from memory.vector_store import search_memory

def build_context(user_input, history):
    memories = search_memory(user_input)

    history_text = "\\n".join([
        f"User: {h['user']}\\nAssistant: {h['assistant']}"
        for h in history[-5:]
    ])

    return f"""
You are a senior engineer agent.

Conversation history:
{history_text}

Relevant memory:
{memories}

User request:
{user_input}
"""
EOF

# ========================
# tools/registry.py
# ========================
cat > tools/registry.py <<EOF
def get_tools():
    return {
        "echo": echo_tool,
        "calc": calc_tool
    }

def echo_tool(input):
    return f"Echo: {input}"

def calc_tool(input):
    try:
        return str(eval(input))
    except:
        return "error"
EOF

# ========================
# tools/executor.py
# ========================
cat > tools/executor.py <<EOF
from tools.registry import get_tools

tools = get_tools()

def execute_tool(name, input):
    if name in tools:
        return tools[name](input)
    return "Tool not found"
EOF

# ========================
# main.py
# ========================
cat > main.py <<EOF
from fastapi import FastAPI
from openai import OpenAI
from context.builder import build_context
from memory.vector_store import save_memory
from memory.session import get_session, save_session
from tools.executor import execute_tool

app = FastAPI()
client = OpenAI()

@app.post("/chat")
async def chat(input: str, session_id: str = "default"):
    history = get_session(session_id)

    context = build_context(input, history)

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=context
    )

    output = response.output[0].content[0].text

    # 简单 tool 触发
    if output.startswith("TOOL:"):
        try:
            _, tool_name, tool_input = output.split(":", 2)
            tool_result = execute_tool(tool_name, tool_input)
            output = f"Tool result: {tool_result}"
        except:
            output = "Tool execution error"

    history.append({"user": input, "assistant": output})
    save_session(session_id, history)

    save_memory(f"Q: {input}\\nA: {output}")

    return {"response": output}
EOF

# 安装依赖
echo "📦 安装依赖..."
pip install -r requirements.txt

# 启动 Redis（Docker）
echo "🧠 启动 Redis..."
docker run -d -p 6379:6379 redis

# 启动服务
echo "🚀 启动服务..."
uvicorn main:app --reload
```
