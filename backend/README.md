# Trendsight Backend

## 1. 模块说明

这是 Trendsight 的 C 后端服务模块，负责为前端提供 API 服务，同时作为系统后端服务层，负责业务逻辑处理、数据库交互，并为 A/B 模块的数据接入提供后端支持。

当前负责：

- FastAPI 后端服务
- 用户认证（JWT 登录认证）
- 用户信息管理与偏好配置
- 智能问答（大模型对话）
- MySQL 数据交互
- 为前端提供后端 API 服务

当前**不负责**：

- 数据采集逻辑（A 模块）
- 算法分析逻辑（B 模块）
- 前端页面展示（D 模块）

## 2. 技术栈

- Python
- FastAPI
- SQLAlchemy
- MySQL + PyMySQL
- JWT + bcrypt
- OpenAI SDK（兼容 OpenAI / DeepSeek / Qwen 等 API）
- Alembic（数据库迁移）

## 3. 项目结构说明

`
backend/
├── routers/        API 路由，定义请求入口
├── services/       业务逻辑层，处理具体业务
├── models/         SQLAlchemy ORM 数据模型
├── schemas/        Pydantic 请求/响应模型
├── utils/          工具函数（密码哈希、JWT 编解码、LLM 调用）
├── alembic/        数据库迁移脚本与配置
├── config.py       配置读取（数据库、JWT、LLM）
├── dependencies.py 公共依赖（数据库会话、JWT 认证）
├── main.py         FastAPI 应用入口
└── requirements.txt 依赖清单
`

各目录职责：

- **routers/** — 注册 HTTP 路由，接收请求并调用 service 层
- **services/** — 实现业务逻辑，操作 ORM 模型
- **models/** — 定义数据库表结构对应的 ORM 类
- **schemas/** — 定义 API 请求体和响应体的 Pydantic 模型
- **utils/** — 无状态工具函数（密码哈希、JWT 编解码、LLM API 调用）
- **alembic/** — 数据库版本迁移管理

## 4. 环境配置

### 配置文件

复制环境变量模板并重命名为 .env：

`ash
copy .env.example .env
`

### 环境变量说明

| 变量 | 说明 | 默认值 |
|---|---|---|
| DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME | MySQL 数据库连接信息 | localhost:3306 / root / trendsight |
| JWT_SECRET_KEY | JWT 签名密钥 | dev-secret-key |
| JWT_ALGORITHM | JWT 签名算法 | HS256 |
| JWT_EXPIRATION_MINUTES | Token 过期时间（分钟） | 1440（24小时） |
| LLM_API_KEY | 大模型 API 密钥 | 无默认值，必须配置 |
| LLM_BASE_URL | 大模型 API 地址 | https://api.openai.com/v1 |
| LLM_MODEL | 大模型名称 | gpt-4o-mini |

### LLM 配置说明

LLM 接入采用 OpenAI API 兼容方式。通过修改 LLM_BASE_URL 和 LLM_MODEL 可切换不同模型服务：

| 服务商 | LLM_BASE_URL | LLM_MODEL 示例 |
|---|---|---|
| OpenAI | https://api.openai.com/v1 | gpt-4o, gpt-4o-mini |
| DeepSeek | https://api.deepseek.com | deepseek-chat |
| 通义千问（阿里云） | https://dashscope.aliyuncs.com/compatible-mode/v1 | qwen-plus |

> .env 包含敏感信息（数据库密码、JWT 密钥、LLM API Key），不会提交到 Git。

## 5. 本地启动方式

进入目录：

`ash
cd backend
`

安装依赖：

`ash
pip install -r requirements.txt
`

启动服务：

`ash
uvicorn main:app --reload --port 8000
`

访问 API 文档（Swagger）：

`
http://127.0.0.1:8000/docs
`

## 6. 数据库

### 数据库表

当前后端使用 MySQL 数据库，现有以下数据表：

| 表名 | 说明 |
|---|---|
| users | 用户账号与密码哈希 |
| user_preferences | 用户偏好配置（关注领域、关键词、平台网址） |
| conversations | 智能问答对话记录 |
| messages | 对话消息明细（role / content / created_at） |

> conversations 表中的 event_id 字段为事件关联预留字段，当前与 Event 表解耦，不依赖 events 表。

### 数据库迁移

项目使用 Alembic 管理数据库版本迁移。

首次建表：

`ash
cd backend
alembic upgrade head
`

查看当前版本：

`ash
alembic current
`

查看迁移历史：

`ash
alembic history
`

生成新的迁移脚本（修改 Model 后）：

`ash
alembic revision --autogenerate -m "说明信息"
`

### 初始化工具

| 脚本 | 用途 |
|---|---|
| init_db.py | 创建所有数据库表（基于当前 ORM 模型，替代 migration 的快速方式） |
| create_test_user.py | 创建开发测试用户（username=test, password=123456） |

执行顺序：

`ash
python init_db.py
python create_test_user.py
`

## 7. 当前已实现接口

### 认证模块

#### POST /api/auth/login

- **用途**：用户登录
- **请求体**：用户名和密码
- **成功返回**：用户信息和 JWT Token

#### GET /api/user/profile

- **用途**：获取当前登录用户信息
- **需要**：Authorization: Bearer <token>

#### PUT /api/user/preferences

- **用途**：更新用户偏好配置
- **需要**：Authorization: Bearer <token>
- **请求体**：关注领域、关注关键词、关注平台网址

### 智能问答模块（QA）

#### POST /api/events/{event_id}/qa

- **用途**：用户针对舆情事件提问，大模型回答
- **需要**：Authorization: Bearer <token>
- **请求体**：
  - conversation_id（可选）：已有对话 ID，为空则创建新对话
  - question（必填）：用户问题
- **返回**：conversation_id、nswer、created_time

能力说明：

- 首次提问自动创建新会话并生成 conversation_id
- 传入已有 conversation_id 可延续多轮对话
- 每次对话自动保存消息到数据库（messages 表）
- 支持多轮对话上下文（历史消息随每次提问传入 LLM）

#### GET /api/qa/history/{conversation_id}

- **用途**：获取指定对话的聊天记录
- **需要**：Authorization: Bearer <token>
- **返回**：conversation_id、messages（role / content / created_time）

> 未来业务接口会根据 A/B 模块开发情况调整，最终接口定义以 pi-design/ 中的接口契约为准。

## 8. 前后端联调说明

### 登录流程

1. 用户输入 username 和 password
2. 前端调用 POST /api/auth/login
3. 后端返回 JWT Token
4. 前端保存 Token（如 localStorage）
5. 后续请求在 HTTP Header 中携带 Authorization: Bearer <token>

### 问答流程

1. 用户输入问题
2. 前端调用 POST /api/events/{event_id}/qa
3. 首次提问不传 conversation_id，后端返回新生成的 ID
4. 后续提问携带返回的 conversation_id，实现多轮对话
5. 前端可调用 GET /api/qa/history/{conversation_id} 获取历史记录

## 9. Git 注意事项

以下文件包含敏感信息或个人开发规范，**不会提交到 Git**：

- AGENTS.md — 个人开发规范
- .env — 数据库密码、JWT 密钥、LLM API Key 等敏感配置
- ackend/.env — 同上
- __pycache__/ 和 .pyc 文件 — Python 缓存

.env.example 作为配置模板可以正常提交。

LLM API Key 等敏感信息通过 .env 文件管理，不硬编码在代码中。
