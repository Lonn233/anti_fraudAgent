# Anti-Fraud 智能体助手后端（FastAPI）

## 功能
- 注册/登录（JWT Bearer）
- 设置/读取用户基础信息：年龄、工作、地区
- 监护人管理：新增/列表/删除（绑定到当前用户）
- 反诈识别：
  - 文字识别：提交文本，返回风险评分与原因
  - 媒体识别：上传图片/语音/视频文件，保存文件并返回风险评分与原因（当前为可替换的占位规则引擎）
- 知识库：`POST /kb/text/upload` 上传长文本 → 分段 → 调用 **Doubao-embedding-vision**（火山方舟 `/embeddings`）→ 写入 **Milvus**

## 本地启动（Windows / PowerShell）
1) 创建虚拟环境并安装依赖

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) 配置环境变量
- 复制 `.env.example` 为 `.env`（如需自定义数据库路径、上传目录等可在此修改）

3) 启动

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

打开接口文档：`http://127.0.0.1:8000/docs`

## 主要接口（摘要）
- `POST /auth/register`
- `POST /auth/login`（表单登录，返回 `access_token`）
- `POST /auth/login/json`（JSON 登录，返回 `access_token`）
- `GET /users/me`
- `PUT /users/me/profile`
- `POST /guardians` / `GET /guardians` / `DELETE /guardians/{guardian_id}`
- `POST /detect/text`
- `POST /detect/media`（multipart `file` + `media_type`）
- `GET /detect/records`（当前用户识别记录）
- `POST /kb/text/upload`（JSON：`text`；可选 `doc_id`、`chunk_max_chars`、`chunk_overlap_chars`；需 JWT，依赖 Milvus + 方舟 API Key）

## 鉴权方式（JWT Bearer）
除 `/health`、`/auth/register`、`/auth/login`、`/auth/login/json` 外，其它接口都需要携带 Bearer Token：

1) 先调用 `POST /auth/login` 或 `POST /auth/login/json` 获取 `access_token`
2) 在 Swagger `/docs` 里点右上角 `Authorize`，填入：
   - `Bearer <access_token>`

## 知识库 / Milvus / 豆包向量化
1) 本地或云端启动 **Milvus**（默认连 `http://127.0.0.1:19530`）。
2) 在 `.env` 中配置 `DOUBAO_API_KEY`，必要时修改：
   - `DOUBAO_ARK_BASE_URL`（默认方舟 `.../api/v3`）
   - `DOUBAO_EMBEDDING_MODEL`（默认 `doubao-embedding-vision-251215`，按控制台实际模型名修改）
   - `MILVUS_EMBEDDING_DIM`（需与模型输出维度一致，常见 1024 / 2048）
3) 安装依赖：`pip install -r requirements.txt`

说明：向量化请求按火山方舟 **OpenAI 兼容** `POST {DOUBAO_ARK_BASE_URL}/embeddings`，body 为 `model` + `input`（文本分段列表）。若你使用的接入方式或请求体与文档不一致，可在 `app/services/doubao_embed.py` 中调整。

## 目录结构
- `app/main.py`：入口
- `app/config/settings.py`：配置（读取 `.env`）
- `app/db/session.py`：数据库连接与 Session
- `app/db/models.py`：SQLAlchemy 模型
- `app/schemas.py`：Pydantic 入参/出参
- `app/utils/security.py`：密码哈希（`pbkdf2_sha256`）+ JWT 编解码
- `app/utils/deps.py`：鉴权依赖（`get_current_user`）
- `app/services/anti_fraud.py`：反诈识别逻辑（当前为可替换占位规则引擎）
- `app/services/text_chunk.py`、`doubao_embed.py`、`milvus_text.py`：知识库分段、嵌入、Milvus 写入
- `app/api/*`：各业务路由（auth/users/guardians/detect/knowledge）
