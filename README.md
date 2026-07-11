# Trendsight — 网络舆情事件智能分析系统

针对突发公共事件和社会热点话题，实现多源数据采集、热点事件识别、情感分析、趋势预测和智能问答。

## 系统架构

```
A 爬虫（web_crawler）
  └─ 新浪新闻 / 微博 / 知乎 多平台采集
        ↓
B 算法（algo — FastAPI 服务）
  └─ 清洗去重 → 事件聚类 → 情感分析 → 热度/生命周期预测
        ↓
C 后端（backend — FastAPI + MySQL）
  └─ 调用 B 触发分析，整合结果，提供 RESTful API
        ↓
D 前端（frontend — React + ECharts）
  └─ 事件看板 / 分析报告 / 智能问答
```

## 模块说明

| 目录 | 模块 | 职责 |
|------|------|------|
| `web_crawler/` | A — 数据采集 | 新浪新闻、微博、知乎三平台爬虫，含信源认证类型识别 |
| `algo/` | B — 算法分析 | NLP 分析 FastAPI 服务，不直接访问数据库 |
| `backend/` | C — 后端服务 | FastAPI + SQLAlchemy，调用 B 并持久化结果 |
| `frontend/` | D — 前端展示 | React + ECharts，数据可视化与智能问答 |
| `api-design/` | — 接口契约 | 后端 API 路径与字段定义文档 |

## 主要功能

- **热点事件发现**：TF-IDF 相似度 Single-Pass 增量聚类，自动识别事件簇
- **情感分析**：RoBERTa 预训练模型（评论）+ 词典法降级，区分帖子与评论
- **生命周期预测**：潜伏 / 成长 / 高潮 / 衰退四阶段 + 未来趋势线性外推
- **风险等级**：基于热度 × 负面情感的规则法，分 high / mid_high / mid / low
- **智能问答**：基于大模型的事件专项多轮对话
- **信源可信度**：爬虫采集 `verification_type`（官方平台 / 认证机构 / 普通用户等）
- **事件排序**：支持按热度（heat）/ 时间（event_time）/ 负面情感（negative）对事件列表进行排序

## 模块间交互

```
A 爬虫定时写入 MySQL（raw_documents / raw_comments）
        ↓
C 后端读取原始数据 → POST /analyze → B 算法服务
        ↓
B 返回分析结果（事件聚类 + 情感 + 关键词 + 趋势）
        ↓
C 持久化到 events / event_keywords / event_platforms / event_trend_daily
        ↓
D 前端调用 C 的 /api/events/* 接口展示
```

## 各模块文档

- 算法模块：[algo/README.md](algo/README.md)
- 接口设计：[api-design/README.md](api-design/README.md)
- 后端模块：[backend/README.md](backend/README.md)
- 爬虫模块：[web_crawler/docs/data_interface.md](web_crawler/docs/data_interface.md)
