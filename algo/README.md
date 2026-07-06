# algo — 舆情分析算法模块

对应 `docs/algorithm-plan.md` 中的 M1（基础打通）：数据预处理、分词/关键词、
简单热度打分、词典法情感分析。后续里程碑（事件聚类聚合、BERT情感、生命周期
预测、虚假文本检测、传播路径溯源）在此结构基础上继续添加子模块。

## 目录结构

- `algo/schema.py` — 贯穿各阶段的标准 `Document` 数据结构
- `algo/preprocess/` — 去重（SimHash）、正文清洗、字段标准化
- `algo/nlp/` — 分词（jieba，无 jieba 时降级为字符切分）、TF-IDF 关键词提取
- `algo/cluster/` — 热度打分（报道量 + 时间衰减）
- `algo/sentiment/` — 词典法情感分类
- `algo/pipeline.py` — 串联以上模块的端到端流程（`event_id` 分组 → 去重 → 分词 →
  关键词/热度/情感），产出对应"事件详情分析报告"的结构化结果
- `algo/sample_data.py` — 3 个虚构事件、17 条假新闻/帖子（含 2 组刻意构造的
  转载近重复文本），用于在没有真实爬虫数据前跑通整条分析流程
- `run_demo.py` — 用假数据运行整条 pipeline 并打印 JSON 报告

## 运行测试

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

## 用假数据跑通分析流程

```bash
python run_demo.py
```

会对 3 个虚构事件（暴雨地铁进水/手机新品发布/高校食堂食品安全）各自输出：
报道数（去重后）、去重条数、热度分值、情感分布（正/负/中性占比）、高频关键词、
来源/平台列表、时间跨度。注意 `run_demo.py` 里把 SimHash 去重阈值调到了 20 ——
默认阈值 3 是按完整长文章调的，本次假数据是单段短文本，个别措辞改动占比更大，
对应的近重复文本汉明距离天然更大，实际接入真实长文章时应改回更严格的阈值。

## 已知局限（等后续里程碑再完善）

- 事件分组目前直接用假数据里预置的 `event_id`；真正的事件聚类（Single-Pass）在 M2。
- 词典法情感分析是逐 token 子串匹配，处理不了否定结构（如"不满意"里刚好包含
  positive 词"满意"），M2 换成 BERT 分类器后会好很多。
- 无 jieba 环境下的降级分词是按字切分，词典法情感因此基本失效（词典词是词语级），
  仅用于保证流程不崩溃，不代表实际效果。
