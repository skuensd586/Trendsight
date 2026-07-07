# algo — 舆情分析算法模块

对应 `docs/algorithm-plan.md` 中的 M1（基础打通）+ M2 起步（事件聚类）+ M3 起步
（生命周期/变点检测）：数据预处理、分词/关键词、简单热度打分、词典法情感分析、
Single-Pass 事件聚类、生命周期阶段判断、变点检测。后续里程碑（BERT 情感、虚假
文本检测、传播路径溯源）在此结构基础上继续添加子模块。

## 目录结构

- `algo/schema.py` — 贯穿各阶段的标准 `Document` 数据结构
- `algo/preprocess/` — 去重（SimHash）、正文清洗、字段标准化
- `algo/nlp/` — 分词（jieba，无 jieba 时降级为字符切分）、TF-IDF 关键词提取/向量化
- `algo/cluster/` — 热度打分（报道量 + 时间衰减）、Single-Pass 事件聚类、聚类纯度评估
- `algo/sentiment/` — 词典法情感分类（`dict_sentiment.py`）+ 机器学习情感分类
  （`ml_sentiment.py`，见下方"机器学习情感分类"一节），二者是平行方案，`pipeline.py`
  目前仍走词典法
- `algo/trend/` — 报道量分桶、生命周期阶段判断（潜伏/成长/高潮/衰退）、变点检测
  （关键时间节点，z-score 简化版，非完整 PELT）
- `algo/pipeline.py` — 串联以上模块的端到端流程：`discover_events`（聚类发现事件）→
  `run_pipeline`（按 event_id 分组 → 去重 → 分词 → 关键词/热度/情感/趋势），
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

## 用假数据跑通生命周期/趋势判断（M3 起步）

`run_demo.py` 的输出里现在每个事件都带 `stage`（latent/growth/peak/decline）、
`trend`（按日聚合的报道量时间序列，前端"发展趋势图"直接能用）、`future_trend`
（对 `trend` 做简单线性外推的未来预测）、`key_timepoints`（变点检测标出的关键时间
节点）。样本数据里 3 个事件在快照时刻（07-06 18:00）都已过了报道高峰，因此都判为
"decline"——这是真实计算结果，不是凑出来的；暴雨事件的变点检测准确抓到了"初期
集中报道后骤降"的那个时间点。

## 机器学习情感分类（词典法的平行方案）

`sentiment/ml_sentiment.py` 提供 `predict_sentiment(text, text_type="auto") -> "positive"/
"negative"/"neutral"`，是 `dict_sentiment.classify_sentiment` 之外的另一套实现：训练一个
TF-IDF + 分类器（`scripts/train_sentiment_model.py` 里对比 MultinomialNB 和
LogisticRegression，选测试集 accuracy 更高的那个）。分类器本身是二分类（正/负），
两类概率若都低于置信度阈值（默认 0.6）则判为 neutral，这个阈值判断逻辑封装在
`ml_sentiment.label_from_proba`，训练脚本评估和线上预测共用同一份，不会出现"训练时
统计的 neutral 判定标准和线上不一致"的问题。

**为什么按 text_type 分开训练模型**：现在能拿到的公开标注数据基本是微博评论（短、
口语化），但系统实际要分析的还有新闻报道正文（长、书面化），文风差异大，一个模型
硬套两种文本大概率有效果落差（领域迁移问题）。所以模型按 `text_type`
（`comment`/`article`）分开训练、分开加载，命名成
`models/sentiment_model_{text_type}_{训练日期}.joblib`。

**text_type 从哪来**：不是每次调用现猜的，而是在预处理阶段（`preprocess/clean.py`
的 `normalize_document`）就通过平台名查表定下来，写进 `Document.text_type`，一路带到
情感分析这一步。映射表在 `preprocess/text_type.py`（`PLATFORM_TEXT_TYPES`），按平台
名（微博/论坛→comment，新闻客户端/官方网站/官网→article）查，查不到的平台归为
`"auto"`。`predict_sentiment` 的 `text_type="auto"` 只是这张表查不到时的降级兜底
（按文本长度简单猜，阈值 `AUTO_LENGTH_THRESHOLD=200` 字符，代码里明确注释了这只是
权宜规则），不是主要判断方式——调用方应该传 `doc.text_type`，而不是每次自己猜。

**当前过渡状态**：只训了 `comment` 模型，`article` 模型还没有标注数据可训。请求
`text_type="article"` 时会自动回退到 `comment` 模型（首次回退打印一条 warning 日志，
之后不再重复打印），效果可能打折扣但不会报错崩溃。用 `get_model_status()` 能看到
每个 text_type 实际用的是哪个模型文件、是不是在回退状态。等以后有了新闻标注数据，
跑一遍 `scripts/train_sentiment_model.py --text-type article --data ...` 训出
article 模型放进 `models/` 目录，`predict_sentiment` 会自动切换过去，**调用方代码
不需要改一行**。

### 训练模型

```bash
python -m scripts.train_sentiment_model --text-type comment --data path/to/labeled.csv
```

- 数据是两列 CSV/TSV：`label`（0/1 或 neg/pos，不接受 neutral——neutral 是运行时置信度
  阈值判出来的，不是训练出来的类别）、`text`。
- 按 8:2 划分 train/test（固定随机种子），特征提取用 sklearn 的 `TfidfVectorizer`，
  `tokenizer` 直接复用 `nlp/tokenize.py` 的 `tokenize`，训练和线上用同一套分词标准。
- 测试集上对比 MultinomialNB / LogisticRegression 的 accuracy、precision/recall/F1、
  混淆矩阵，选更好的那个保存，结果同时打印到终端和追加进
  `reports/sentiment_training_report.md`。
- `--text-type` 参数决定这次训的是哪个类型，脚本本身不关心这个字符串具体是什么——
  以后喂一份新闻标注数据、参数换成 `--text-type article`，不用改脚本代码。

### 验证领域迁移

```bash
python -m scripts.validate_domain_shift --text-type comment --data-text-type article --data path/to/small_labeled.csv
```

用指定 text_type 的模型跑一遍任意标注验证集，算 accuracy，结果追加进同一份报告，
注明"用 X 类型模型评估 Y 类型文本"。工具本身不关心 X/Y 具体是什么，所以以后训出
article 模型了，反过来跑 `--text-type article --data-text-type comment` 验证"文章
模型在评论文本上表现如何"，用的是同一个工具。

## 对齐后端 api-design 接口

`main` 分支新增了 `api-design/`（`events.json`、`prediction.json` 等），定义了后端
（C 模块）期望从算法模块（B 模块）拿到的字段名和形状。`pipeline.py` 的输出字段已经
按这份契约改过一轮：

|字段|来源|对应接口|
|-|-|-|
|`heat`|`cluster.compute_hotness`|README 里 B 模块的输出字段说明|
|`sentiment.{positive,neutral,negative}`|`sentiment.classify_sentiment`|`/api/events/{id}/sentiment`|
|`keywords: [{word, weight}]`|`nlp.extract_keywords`，weight 按最高分归一化到 0-1|`/api/events/{id}/keywords`|
|`platform_distribution: [{platform_name, ratio}]`|按 `Document.platform` 计数|`/api/events/{id}/platform`|
|`trend: [{date, count}]`|`trend.daily_report_counts`，按自然日聚合|`/api/events/{id}/trend`|
|`stage`（latent/growth/peak/decline）、`confidence`、`stage_probability`、`analysis`、`future_trend`|`trend.predict_lifecycle` + `trend.forecast_future_trend`|`/api/events/{id}/lifecycle`|

**没对上/需要跟后端同步的地方：**

- `main` 分支的 `events.json` 文件内容目前和 `auth.json` 几乎一样（`module` 字段写的是
  `"auth"`，且缺了 README 里提到的"热点事件列表"`/api/events/hot`和"事件详情"
  `/api/events/{event_id}` 这两个接口定义）——像是重命名 `event.json → events.json` 时
  操作失误，建议跟负责后端接口设计的同学确认一下。
- `stage_probability`/`confidence` 是规则法的启发式置信度（越多分桶数据置信度越高，
  上限 0.9；相邻阶段分走剩余概率），不是训练模型输出的真实后验概率——见
  `trend/lifecycle.py` 里的说明，等换成真实分类模型后应该重新设计这部分。
- `key_timepoints`（关键时间节点）是原始需求文档里提到的功能，但目前 `events.json`/
  `prediction.json` 都没有对应字段，先作为报告里的额外字段保留，等后端加了字段位置
  再对齐。
- `risk_level`（风险等级）在 README 的模块说明里被列为 B 的输出之一，但还没有具体
  JSON 字段定义，所以暂未实现，等接口定下来再补。
- `event_id` 接口里类型是 `integer`（数据库自增主键），算法模块内部用的是字符串型
  聚类标签（如 `cluster-3`）——这层映射预期由后端在入库时处理，算法模块不需要感知
  真实数据库 ID。

## 已知局限（等后续里程碑再完善）

- Single-Pass 聚类的 IDF 是对整批数据一次性算好的，不是真流式增量更新；相似度
  阈值（默认 0.04）是在样本数据上扫出来的，换语料要重新调。
- 生命周期阶段判断是规则法（基于分桶报道量的峰值位置和衰减比例），不是曲线拟合
  （Logistic/SIR）；变点检测是一阶差分 z-score 的简化版，不是完整 PELT 算法
  （`docs/algorithm-plan.md` 提到的 `ruptures` 库）——量少的场景下这类简化方法足够
  用，报道量大、噪声多的真实数据可能需要换成更严格的实现。
- 词典法情感分析是逐 token 子串匹配，处理不了否定结构（如"不满意"里刚好包含
  positive 词"满意"），M2 换成 BERT 分类器后会好很多。
- 无 jieba 环境下的降级分词是按字切分，词典法情感因此基本失效（词典词是词语级），
  仅用于保证流程不崩溃，不代表实际效果。
- `ml_sentiment` 目前没有真实训练过的模型（`models/` 目录是空的），需要先跑
  `scripts/train_sentiment_model.py` 才能用；本仓库没有提交任何"看起来训练过"的
  模型文件或报告条目，避免误导——真跑过的一次烟雾测试用的是自造假数据，只验证了
  代码能跑通，不代表真实准确率（详见开发过程记录）。
- `ml_sentiment` 的分类器核心是二分类（正/负），neutral 是概率都低于阈值时的运行时
  判定，不是训练出来的第三个类别；`article` 模型没训之前一直靠 `comment` 模型兜底，
  真实效果如何要等有了新闻标注数据、跑一遍 `validate_domain_shift.py` 才知道。
