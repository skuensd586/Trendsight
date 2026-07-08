# Trendsight — 网络舆情事件智能分析系统

针对突发公共事件和社会热点话题，实现多源数据采集、热点事件识别、情感分析、趋势预测和智能问答。

## 系统架构

```
A 爬虫（Crawler）
  └─ 采集新闻/社交平台原始数据
        ↓
B 算法（Algorithm / NLP）       ← 本仓库 algo/
  └─ 清洗去重 → 事件聚类 → 情感分析 → 热度/生命周期预测
        ↓
C 后端（Backend API）
  └─ 整合 A/B 数据，提供 RESTful API
        ↓
D 前端（Frontend）
  └─ 事件看板 / 分析报告 / 智能问答
```

## 模块说明

| 目录 | 模块 | 职责 |
|------|------|------|
| `algo/` | B — 算法分析 | 预处理、NLP、事件聚类、情感分析、趋势预测 |
| `sina_crawler/` | A — 数据采集 | 新浪新闻爬虫，写入 raw_documents |
| `api-design/` | C — 接口契约 | B→C 字段定义（events/prediction/qa） |

## 算法模块快速上手

```bash
cd algo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 用假数据跑通全流程
python run_demo.py

# 跑测试
pytest
```

### 训练情感分类模型

```bash
# 下载开源评论标注数据（ChnSentiCorp，~7.7k 条）
python -m scripts.download_sentiment_data

# 训练（LogisticRegression，held-out accuracy ~0.81）
python -m scripts.train_sentiment_model --text-type comment --data data/sentiment_comment.csv
```

模型保存至 `algo/models/`，训练报告追加至 `algo/reports/sentiment_training_report.md`。

## 算法模块输出字段

pipeline 对每个事件输出以下结构化结果，由后端 C 封装为 API：

| 字段 | 含义 |
|------|------|
| `heat` | 事件热度指数（报道量 × 时间衰减） |
| `sentiment` | 正/中/负情感占比 |
| `keywords` | 高频关键词及权重 |
| `stage` | 生命周期阶段（latent / growth / peak / decline） |
| `future_trend` | 未来报道量线性外推 |
| `key_timepoints` | 变点检测标出的关键时间节点 |
| `platform_distribution` | 各平台来源占比 |

## 接口契约

见 `api-design/README.md`，定义了 C 后端暴露给前端 D 的全部 API 路径和字段格式。
