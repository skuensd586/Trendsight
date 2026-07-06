# algo — 舆情分析算法模块

对应 `docs/algorithm-plan.md` 中的 M1（基础打通）+ M2 起步（事件聚类）：数据预处理、
分词/关键词、简单热度打分、词典法情感分析、Single-Pass 事件聚类。后续里程碑
（BERT 情感、生命周期预测、虚假文本检测、传播路径溯源）在此结构基础上继续添加子模块。

## 目录结构

- `algo/schema.py` — 贯穿各阶段的标准 `Document` 数据结构
- `algo/preprocess/` — 去重（SimHash）、正文清洗、字段标准化
- `algo/nlp/` — 分词（jieba，无 jieba 时降级为字符切分）、TF-IDF 关键词提取/向量化
- `algo/cluster/` — 热度打分（报道量 + 时间衰减）、Single-Pass 事件聚类、聚类纯度评估
- `algo/sentiment/` — 词典法情感分类
- `algo/pipeline.py` — 串联以上模块的端到端流程：`discover_events`（聚类发现事件）→
  `run_pipeline`（按 event_id 分组 → 去重 → 分词 → 关键词/热度/情感），
  产出对应"事件详情分析报告"的结构化结果
- `algo/sample_data.py` — 3 个虚构事件、17 条假新闻/帖子（含 2 组刻意构造的
  转载近重复文本），用于在没有真实爬虫数据前跑通整条分析流程
- `run_demo.py` — 用假数据 + 已知 event_id 运行整条 pipeline 并打印 JSON 报告
- `run_demo_cluster.py` — 去掉假数据的 event_id 标签，跑 Single-Pass 聚类自动发现事件，
  再对比真实标签算聚类纯度，验证"不依赖预先分组"也能跑通

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

## 用假数据跑通事件聚类（M2）

```bash
python run_demo_cluster.py
```

不给聚类算法任何真实 event_id，纯靠 TF-IDF 余弦相似度做 Single-Pass 增量聚类，
再用聚类纯度（purity）对比真实标签评估效果。当前在样本数据上纯度 1.0（3个真实
事件、17条记录聚出4个簇）——多出的一个簇是"手机发布"事件被拆成了"发布"和"上手
评测"两个子簇：这两批报道用词重合度低（TF-IDF 只看字面重叠），是词袋方法的真实
局限，后续换成语义向量（Sentence-BERT 等）应该能改善。

## 已知局限（等后续里程碑再完善）

- Single-Pass 聚类的 IDF 是对整批数据一次性算好的，不是真流式增量更新；相似度
  阈值（默认 0.04）是在样本数据上扫出来的，换语料要重新调。
- 词典法情感分析是逐 token 子串匹配，处理不了否定结构（如"不满意"里刚好包含
  positive 词"满意"），M2 换成 BERT 分类器后会好很多。
- 无 jieba 环境下的降级分词是按字切分，词典法情感因此基本失效（词典词是词语级），
  仅用于保证流程不崩溃，不代表实际效果。
