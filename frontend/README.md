# Trendsight Frontend

Trendsight 前端为 Vite + React 项目，默认使用 mock 数据运行。

## 启动

```bash
npm install
npm run dev
```

看板地址：

```text
http://localhost:5173/dashboard
```

## 接口模式

复制 `.env.example` 为 `.env` 后可切换接口模式：

```env
VITE_API_MODE=mock
VITE_API_BASE_URL=http://localhost:8000
```

- `mock`：使用本地 mock 数据。
- `backend`：请求真实后端接口。

接口字段说明见 `docs/`。
