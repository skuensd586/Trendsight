# algo — 舆情分析算法模块（B 模块）

以 FastAPI 服务对外暴露，供 C 后端调用。不直接访问数据库，只负责计算。

## 接口

```
GET  /health     健康检查，返回服务状态和模型加载情况
POST /analyze    主分析接口，输入原始文档和评论，返回事件分析报告列表
```

### POST /analyze 请求体

```json
{
  "documents": [ ...raw_documents 记录... ],
  "comments":  [ ...raw_comments 记录... ],
  "sentiment_method": "bert"
}
```

`sentiment_method` 枚举：`bert`（默认）/ `ml`（TF-IDF+LR）/ `dict`（词典法）

### POST /analyze 返回字段

```json
{
  "events": [
    {
      "title": "...",
      "heat": 60.2,
      "risk_level": "high",
      "stage": "peak",
      "event_time": "2026-07-08T12:00:00",
      "time_start": "...",
      "time_end": "...",
      "report_count": 141,
      "duplicate_count": 3,
      "sentiment": { "positive": 0.62, "neutral": 0.31, "negative": 0.07 },
      "keywords": [ { "word": "水库", "weight": 1.0 }, ... ],
      "platform_distribution": [ { "platform_name": "微博", "ratio": 0.6 }, ... ],
      "sources": ["新浪新闻", "微博"],
      "trend": [ { "date": "2026-07-06", "count": 35 }, ... ],
      "lifecycle": {
        "stage": "peak",
        "confidence": 0.9,
        "stage_probability": { "latent": 0.02, "growth": 0.08, "peak": 0.85, "decline": 0.05 },
        "future_trend": [ { "date": "2026-07-09", "predict_count": 120, "predict_heat": 60 }, ... ],
        "analysis": "..."
      },
      "key_timepoints": [ "2026-07-08T14:49:51", ... ],
      "comment_count": 101
    }
  ]
}
```

## 目录结构

```
algo/
├── server.py              FastAPI 服务入口（lifespan 预热 jieba + BERT）
├── worker.py              本地批量跑用（不部署，仅本地调试）
├── run_demo.py            假数据端到端演示
├── run_demo_cluster.py    假数据事件聚类演示
├── scripts/
│   ├── download_sentiment_data.py   下载 ChnSentiCorp 训练数据
│   ├── train_sentiment_model.py     训练 TF-IDF+LR 情感模型
│   └── validate_domain_shift.py    验证跨领域模型效果
└── algo/
    ├── schema.py          标准 Document 数据结构
    ├── preprocess/        去重（SimHash）、字段标准化、text_type 推断
    ├── nlp/               分词（jieba）、TF-IDF 关键词提取
    ├── cluster/           热度打分、Single-Pass 聚类、质心暴露接口
    ├── sentiment/         词典法 / TF-IDF+LR / RoBERTa 三路情感分析
    ├── trend/             分桶、生命周期判断、变点检测、趋势外推
    └── pipeline.py        端到端流程串联，analyze_event / discover_events
```

## 情感分析三路方案

| 方案 | 实现 | 适用场景 |
|------|------|---------|
| `bert` | `uer/roberta-base-finetuned-jd-binary-chinese` | 默认，适合微博评论 |
| `ml` | TF-IDF + LogisticRegression（ChnSentiCorp 训练）| 无 GPU 或 BERT 未下载时 |
| `dict` | 正负词典子串匹配 | 无模型降级兜底 |

**两阶段流程**（有评论时）：帖子做聚类 → 评论按 TF-IDF 质心分配到对应簇 → 情感由评论计算（信号更强）；热度 / 关键词 / 生命周期 / 趋势由帖子计算。

`text_type` 在预处理阶段由平台名推断（微博 → `comment`，新浪新闻/知乎 → `article`），影响情感模型选择。

## 输出字段说明

| 字段 | 说明 |
|------|------|
| `heat` | 报道量 × 时间衰减热度指数 |
| `risk_level` | `high/mid_high/mid/low`，热度 × 负面情感规则法 |
| `stage` | `latent/growth/peak/decline` 生命周期阶段（顶层快捷字段）|
| `lifecycle` | 完整生命周期对象（含置信度、各阶段概率、未来预测、文字说明）|
| `sentiment` | 情感分布，有评论时来自评论，无评论时来自帖子正文 |
| `comment_count` | 分配到该事件簇的评论数 |
| `key_timepoints` | 变点检测标出的关键时间节点（API 合同暂未定义，作为附加字段）|

## 本地运行

```bash
cd algo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 启动 FastAPI 服务（C 后端调用）
uvicorn server:app --reload --port 8001

# 训练情感模型（可选，无模型时自动降级到词典法）
python -m scripts.download_sentiment_data
python -m scripts.train_sentiment_model --text-type comment --data data/sentiment_comment.csv

# 跑测试
pytest
```

## 对齐爬虫模块（web_crawler）

当前已对接三个平台：

| 平台 | 注册名 | text_type | 备注 |
|------|--------|-----------|------|
| 新浪新闻 | `sina` | `article` | 长篇报道 |
| 微博 | `weibo` | `comment` | 帖子 + 评论 |
| 知乎 | `zhihu` | `article` | 问答长文 |

爬虫新增了 `verification_type` 字段（`官方平台 / 认证机构 / 头部认证个人 / 认证个人 / 普通用户`），B 模块预留用于后续信源可信度分析。

## 对齐后端（backend）

C 后端调用 B 的流程：

1. C 从 MySQL 读取 `clean_status='raw'` 的 `raw_documents` 和 `raw_comments`
2. C 调 `POST /analyze`，B 返回事件分析报告列表
3. C 将报告持久化到 `events`、`event_keywords`、`event_platforms`、`event_trend_daily` 四张表

**注意**：B 输出 `time_start` / `time_end` 为独立字段（非旧版 `time_range` 列表），C 的 `event_service.py` 需确认已对齐此格式。

## 已知局限

- 聚类阈值（0.04）在样本数据上调优，真实大语料可能需要重新调整
- 生命周期判断为规则法，仅有 3-5 天数据时"衰退期"预测不可靠
- `article` 情感模型尚未训练，当前回退到 `comment` 模型（书面语效果有偏差）
- `key_timepoints`（关键时间节点）暂未纳入后端 API 合同，前端趋势图尚未对接
