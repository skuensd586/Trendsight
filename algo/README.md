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

## 运行测试

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```
