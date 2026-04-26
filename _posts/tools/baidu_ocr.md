---
layout:     post
title:      百度 OCR 调用记录
subtitle:   从创建应用到获取 access token 再到发起识别请求的最小备忘
date:       2026-04-25
author:     BY
header-img: img/post-bg-debug.png
catalog: true
tags:
    - OCR
    - Python
    - API
---

>把原始笔记里零散的“建应用 + 拿 token + 调接口”三段内容收拢成一篇能直接回看的调用记录。

## 1. 先明确调用链路

这类接口调用最容易忘的不是某一行 Python 代码，而是整体顺序：

1. 在百度智能云里创建应用
2. 拿到 `API Key` 和 `Secret Key`
3. 先请求 `access_token`
4. 再带着 `access_token` 去请求具体 OCR 接口

原始笔记里最有价值的信息，其实就是这条顺序本身。

## 2. 创建应用后要记住哪些参数

获取 token 时，原始记录里保留了这几个参数：

- `grant_type`：固定为 `client_credentials`
- `client_id`：应用的 `API Key`
- `client_secret`：应用的 `Secret Key`

整理后最重要的提醒是：

> `API Key` 和 `Secret Key` 只适合保存在本地安全环境、环境变量或密钥管理系统中，不要直接写进公开仓库。

## 3. 获取 access token

原始笔记中提到，`access_token` 有有效期，需要定期重新获取。

最小 Python 示例可以整理成下面这样：

```python
import requests


def get_access_token(api_key: str, secret_key: str) -> str:
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret_key,
    }

    response = requests.post(url, params=params, timeout=10)
    response.raise_for_status()

    data = response.json()
    return data["access_token"]


if __name__ == "__main__":
    token = get_access_token("YOUR_API_KEY", "YOUR_SECRET_KEY")
    print(token)
```

### 回看这段时重点确认什么

- `client_id` / `client_secret` 是否对应同一个应用
- 当前应用是否真的开通了 OCR 能力
- token 是否已经过期

## 4. 拿到 token 之后再调用 OCR

原始文档第三段只留下了另一份获取 token 的脚本，没有把真正的 OCR 请求补全。  
为了让这篇笔记更可用，这里整理成一个最小识别请求示例。

以通用文字识别接口为例：

```python
import base64
import requests


def call_general_basic(access_token: str, image_path: str) -> dict:
    url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={access_token}"

    with open(image_path, "rb") as f:
        image_base64 = base64.b64encode(f.read()).decode("utf-8")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    payload = {
        "image": image_base64,
    }

    response = requests.post(url, data=payload, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    result = call_general_basic("YOUR_ACCESS_TOKEN", "/path/to/test.png")
    print(result)
```

## 5. 这篇记录真正想帮自己记住什么

以后回看这篇，优先记住下面三点：

1. 先拿 token，再调 OCR 接口
2. `API Key` / `Secret Key` 不要直接硬编码进公开文档或仓库
3. 如果接口失败，先分清楚是 **鉴权失败** 还是 **OCR 请求本身失败**

## 6. 遇到失败时先排查哪里

如果调用没通，优先按这个顺序看：

1. `API Key` 和 `Secret Key` 是否正确
2. `access_token` 是否过期
3. OCR 接口地址是否写对
4. 图片是否按接口要求编码
5. 当前账号或应用是否开通了目标 OCR 服务

## 7. 最后保留的最小实践建议

- 获取 token 和调用 OCR 最好拆成两个函数
- 密钥放环境变量，不要放源码
- 调试时优先打印 HTTP 状态码和返回 JSON
- 如果只是临时试验，至少也要把示例值改成占位符再保存笔记
