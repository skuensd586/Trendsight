# 前后端接口对齐文档

本文档用于统一 Trendsight 前端与后端的接口口径。处理原则：

- 后端 `api-design` 已经定义的接口、路径、响应包格式，前端按后端修改。
- 后端已经列出路径但没有写清返回字段的接口，字段格式统一放到 [backend-uncovered-contract.example.jsonc](./backend-uncovered-contract.example.jsonc)。
- 后端当前明确未覆盖的高级分析数据，也统一放到该补充文件中，避免散落在页面代码或口头约定里。

## 1. 通用响应格式

后端 README 规定统一响应包如下，前端接入时按这个结构解包：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

说明：

- 旧前端文档里的 `code: 0` / `message: "ok"` 已不再作为对接标准。
- 前端请求层应先判断 `code === 200`，再读取 `data`。
- 错误响应后端可以继续使用同一外层结构，例如 `{ "code": 401, "message": "unauthorized", "data": null }`。

## 1.1 前端接口模式切换

前端已提供两种模式：

```env
VITE_API_MODE=mock
VITE_API_BASE_URL=http://localhost:8000
```

- `VITE_API_MODE=mock`：默认模式，继续读取本地 mock 数据。
- `VITE_API_MODE=backend`：请求真实后端接口，接口基地址读取 `VITE_API_BASE_URL`。

切到真实后端时，复制 `.env.example` 为 `.env`，把 `VITE_API_MODE` 改成 `backend`，再重启前端服务即可。

## 2. 已按后端修改的接口

以下接口以后端 `api-design` 为准，前端不再使用旧文档里的自定义路径。

| 功能 | 后端接口 | 前端处理 |
| --- | --- | --- |
| 登录 | `POST /api/auth/login` | 保存 `data.token`，后续请求带 `Authorization: Bearer <token>` |
| 用户信息 | `GET /api/user/profile` | 用于顶部用户名、个人中心账号信息、关注配置 |
| 更新关注设置 | `PUT /api/user/preferences` | 以 `auth.json` 为准；README 里的 `/api/user/settings` 不再使用 |
| 热点事件列表 | `GET /api/events/hot` | 路径按后端 README；返回字段格式见补充文件 |
| 事件详情主体 | `GET /api/events/{event_id}` | 路径按后端 README；返回字段格式见补充文件 |
| 趋势数据 | `GET /api/events/{event_id}/trend` | 后端字段 `date/count`，前端适配为图表需要的 `time/value` |
| 情感分布 | `GET /api/events/{event_id}/sentiment` | 直接使用 `positive/neutral/negative` |
| 平台分布 | `GET /api/events/{event_id}/platform` | 后端字段 `platform_name/ratio`，前端适配为 `name/value` |
| 关键词 | `GET /api/events/{event_id}/keywords` | 后端字段 `word/weight`，前端适配为词云 `words` |
| 生命周期预测 | `GET /api/events/{event_id}/lifecycle` | 后端阶段值为 `latent/growth/peak/decline`，前端显示时映射成中文 |
| 事件问答 | `POST /api/events/{event_id}/qa` | 发送 `conversation_id/question` |
| 聊天历史 | `GET /api/qa/history/{conversation_id}` | 后端消息字段 `role/content/time`，前端展示时适配为 `role/text/time` |

## 3. 需要前端适配的字段映射

前端当前页面还没有真实请求层，后续接入时建议在统一 API adapter 里做字段映射，不要把映射逻辑散在组件里。

| 后端字段 | 前端现用字段 | 说明 |
| --- | --- | --- |
| `event_id` | `id` | 后端为整数；前端路由可以用字符串形式展示，但数据源以 `event_id` 为准 |
| `risk_level` | `risk` | 补充规范定义英文枚举，前端映射成 `高/中高/中/低` |
| `stage` | `stage` | 后端生命周期使用 `latent/growth/peak/decline`，前端映射成 `潜伏期/成长期/高潮期/衰退期` |
| `event_time` | `time` | 后端建议使用 ISO 或 `YYYY-MM-DD HH:mm:ss`；前端显示为 `YYYY-MM-DD HH:mm` |
| `report_count` | `reportCount` | 用于看板报道数、详情页 KPI、导出简报 |
| `false_confidence` | `falseConfidence` | 后端未覆盖，补充规范定义；数值范围 `0-1` |
| `duplicate_rate` | `duplicateRate` | 后端未覆盖，补充规范定义；建议数值范围 `0-100`，前端显示时加 `%` |
| `platform_distribution[].platform_name` | `platforms[].name` | 平台名 |
| `platform_distribution[].ratio` | `platforms[].value` | 平台占比，范围 `0-100` |
| `trend[].date` | `trend[].time` | 趋势横轴；如果后端返回完整日期，前端截取或格式化显示 |
| `trend[].count` | `trend[].value` | 趋势数值 |
| `keywords[].word` | `words[][0]` | 词云词语 |
| `keywords[].weight` | `words[][1]` | 词云权重 |
| `messages[].content` | `messages[].text` | 问答消息正文 |

## 4. 后端未覆盖但前端需要的内容

后端 README 当前明确暂未包含：

- 虚假文本检测；
- 事件溯源；
- 关键传播路径分析。

前端详情页还需要以下数据：

- 看板事件列表的完整字段；
- 事件详情主体字段；
- 真实性置信度、重复率、真实性因子；
- 溯源节点和边；
- 传播路径桑基图；
- 地域讨论热力点；
- 相似事件；
- 处置建议；
- 采集源频率和运行状态。

这些格式统一见 [backend-uncovered-contract.example.jsonc](./backend-uncovered-contract.example.jsonc)。该文件是 JSONC，字段旁边已经写注释，方便后端直接照着补接口。

## 5. 联调优先级

1. 先实现 `POST /api/auth/login`、`GET /api/user/profile`，让登录态和用户信息稳定。
2. 再实现 `GET /api/events/hot`，看板可以从本地 mock 切到后端数据。
3. 再实现 `GET /api/events/{event_id}` 和四个分析子接口，详情页可以逐步切换。
4. 最后补 `POST /api/events/{event_id}/qa` 和后端未覆盖的高级分析字段。

## 6. 相关文件

- [frontend-api-payloads.example.jsonc](./frontend-api-payloads.example.jsonc)：后端已覆盖接口的请求/响应样例。
- [backend-uncovered-contract.example.jsonc](./backend-uncovered-contract.example.jsonc)：后端未覆盖或未写明字段的补充格式规范。
- [event-detail-payload.example.jsonc](./event-detail-payload.example.jsonc)：旧详情页样例入口，已指向新的补充规范文件。
