# Trendsight Backend

## 1. 模块说明

这是 Trendsight 的 C 后端服务模块，负责为前端提供 API 服务，同时作为系统后端服务层，负责业务逻辑处理、数据库交互，并为 A/B 模块的数据接入提供后端支持。

当前负责：

- FastAPI 后端服务
- 用户认证
- JWT 登录认证
- 用户信息管理
- 用户偏好配置
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
- MySQL
- PyMySQL
- JWT
- bcrypt

## 3. 项目结构说明

`
backend/
├── routers/       API 路由，定义请求入口
├── services/      业务逻辑层，处理具体业务
├── models/        SQLAlchemy ORM 数据模型
├── schemas/       Pydantic 请求/响应模型
├── utils/         工具函数（密码哈希、JWT 编解码）
├── config.py      配置读取
├── dependencies.py 公共依赖（数据库会话、JWT 认证）
├── main.py        FastAPI 应用入口
└── requirements.txt 依赖清单
`

各目录职责：

- **routers/** — 注册 HTTP 路由，接收请求并调用 service 层
- **services/** — 实现业务逻辑，操作 ORM 模型
- **models/** — 定义数据库表结构对应的 ORM 类
- **schemas/** — 定义 API 请求体和响应体的 Pydantic 模型
- **utils/** — 无状态工具函数，不依赖数据库

## 4. 环境配置

复制环境变量模板并重命名为 .env：

`ash
copy .env.example .env
`

.env 文件包含以下配置类别：

- MySQL 数据库连接（主机、端口、用户名、密码、库名）
- JWT 配置（密钥、算法、过期时间）

> .env 包含敏感信息，不会提交到 Git。

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

访问 API 文档：

`
http://127.0.0.1:8000/docs
`

## 6. 数据库初始化

当前后端使用 MySQL 数据库。

当前已确定的数据表：

- **users** — 用户账号与密码哈希
- **user_preferences** — 用户偏好配置（关注领域、关键词、平台网址）

初始化工具：

| 脚本 | 用途 |
|---|---|
| init_db.py | 创建所有数据库表（基于当前 ORM 模型） |
| create_test_user.py | 创建开发测试用户（username=test, password=123456） |

执行顺序：

`ash
python init_db.py
python create_test_user.py
`

## 7. 当前已实现接口

以下为当前已确认并实现的认证相关接口。

### POST /api/auth/login

- **用途**：用户登录
- **请求体**：用户名和密码
- **成功返回**：用户信息和 JWT Token

### GET /api/user/profile

- **用途**：获取当前登录用户信息
- **需要**：Authorization: Bearer <token>

### PUT /api/user/preferences

- **用途**：更新用户偏好配置
- **需要**：Authorization: Bearer <token>
- **请求体**：关注领域、关注关键词、关注平台网址

> 未来业务接口会根据 A/B 模块开发情况调整，最终接口定义以 pi-design/ 中的接口契约为准。

## 8. 前后端联调说明

前端登录流程：

1. 用户输入 username 和 password
2. 前端调用 POST /api/auth/login
3. 后端返回 JWT Token
4. 前端保存 Token（如 localStorage）
5. 后续请求在 HTTP Header 中携带 Authorization: Bearer <token>

## 9. Git 注意事项

以下文件包含敏感信息或个人开发规范，**不会提交到 Git**：

- AGENTS.md — 个人开发规范
- .env — 数据库密码、JWT 密钥等敏感配置
- ackend/.env — 同上

ackend/.env.example 作为配置模板可以正常提交。
