# Anti-Fraud 智能反诈助手

## 项目简介
本项目是一个基于 FastAPI 的智能反诈辅助系统，集成用户认证、反诈检测、历史记录、监护关系管理与知识库检索能力。系统支持文本、多媒体材料接入，并结合大模型与向量检索对可疑内容进行分析，输出风险判断、防范建议和检测记录。后端提供标准 HTTP API，适合本地运行、二次开发和部署到服务器，前端可直接对接现有接口完成完整业务流程。

## 部署教程

### 1. 环境准备
建议环境：
- Python 3.10+
- Milvus
- 可用的大模型 API Key（豆包 / 火山方舟）

安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell：

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 配置 API Key 与环境变量
项目通过根目录下的 `.env` 读取配置，至少需要检查以下项目：

```env
DOUBAO_API_KEY="你的大模型 API Key"
DOUBAO_ARK_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
DOUBAO_EMBEDDING_MODEL="doubao-embedding-vision-250615"
DOUBAO_CHAT_MODEL="doubao-seed-2-0-mini-260215"
MILVUS_URI="http://127.0.0.1:19530"
MILVUS_COLLECTION="anti_fraud_text_kb"
MILVUS_EMBEDDING_DIM=2048
JWT_SECRET_KEY="请替换为你自己的安全密钥"
PUBLIC_BASE_URL="http://127.0.0.1:8010"
```

如果是服务器部署，请务必修改：
- `DOUBAO_API_KEY`
- `JWT_SECRET_KEY`
- `PUBLIC_BASE_URL`
- 与 Milvus 相关的连接配置

### 3. 启动 Milvus
如果你使用 Docker，可参考如下命令启动 Milvus：

```bash
docker compose up -d
```

如果你的环境没有现成的 `docker-compose.yml`，也可以按 Milvus 官方文档部署，并确保 `.env` 中的 `MILVUS_URI` 指向正确地址。

### 4. 启动项目
本地开发启动：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

服务器部署可使用：

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8010
```

启动后可先访问健康检查或文档页面确认服务正常。

## 接口文档 URL
启动成功后，可通过以下地址查看接口文档：

- Swagger UI：`http://127.0.0.1:8010/docs`
- ReDoc：`http://127.0.0.1:8010/redoc`

如果部署到服务器，请将 `127.0.0.1:8010` 替换为你的实际域名或服务器地址。
