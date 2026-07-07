# 网络舆情事件智能分析系统 API Design

## 1. 项目简介

本目录用于存放网络舆情事件智能分析系统的 API 接口设计文档。

系统面向突发公共事件、社会热点话题等网络舆情信息，实现：

- 多源舆情数据采集
- 热点事件识别
- 舆情趋势分析
- 情感倾向分析
- 事件生命周期预测
- 智能问答

后端服务模块（C）通过 API 接口整合数据采集模块（A）和算法分析模块（B）的结果，为前端模块（D）提供统一的数据访问接口。

---

# 2. API 文件结构

```text
api-design/

├── auth.json
│   用户认证及个人配置相关接口

├── events.json
│   舆情事件展示与分析相关接口

├── qa.json
│   大模型智能问答相关接口

├── prediction.json
│   舆情生命周期预测相关接口

└── README.md
    API设计说明文档
```

---

# 3. 系统模块协作关系

## A：数据采集模块（Crawler）

负责：

- 新闻网站、社交平台数据采集
- 新闻正文获取
- 数据清洗与格式标准化


提供的数据主要包括：

```text
title              新闻标题

content            新闻正文

publish_time       发布时间

source             数据来源

platform           发布平台

event_time         事件发生时间
```

A 模块负责提供原始舆情数据，不直接参与前端展示。

---

## B：算法分析模块（NLP / Machine Learning）

负责：

- 文本分析
- 自动分词
- 关键词提取
- 热点事件发现
- 事件聚合
- 情感分析
- 热度计算
- 生命周期预测


主要输出：

```text
heat              事件热度指数

sentiment         情感倾向比例

keywords          高频关键词

stage             生命周期阶段

risk_level        风险等级

future_trend      未来趋势预测
```

B 模块产生分析结果，由 C 后端封装为 API 返回给前端。

---

## C：后端服务模块

负责：

- 用户登录认证
- API接口设计
- 数据整合
- 数据查询
- 分页排序
- 大模型接口调用
- 聊天记录保存
- 向前端提供统一 JSON 数据


C 模块的数据流：

```text
A 原始数据
+
B 算法分析结果

        ↓

C 后端整合

        ↓

API接口

        ↓

D 前端展示
```

---

## D：前端展示模块

负责：

- 登录页面
- 舆情事件看板
- 事件详情分析报告
- 数据可视化图表
- 智能问答页面
- 个人中心


D 模块通过调用 C 提供的 API 获取数据，不直接访问数据库。

---

# 4. API 模块说明

## 4.1 用户认证模块（auth.json）

功能：

- 用户登录
- 获取用户信息
- 更新用户关注设置


主要接口：

```text
POST /api/auth/login

GET /api/user/profile

PUT /api/user/settings
```


对应功能：

|接口|功能|
|-|-|
|登录接口|用户身份认证|
|用户信息接口|获取用户资料|
|更新设置接口|管理关注平台和关键词|

---

# 4.2 舆情事件模块（events.json）

功能：

提供热点事件展示以及事件分析报告数据。


主要接口：

```text
GET /api/events/hot

GET /api/events/{event_id}

GET /api/events/{event_id}/trend

GET /api/events/{event_id}/sentiment

GET /api/events/{event_id}/platform

GET /api/events/{event_id}/keywords
```


接口作用：

|接口|用途|
|-|-|
|热点事件列表|首页舆情事件看板|
|事件详情|事件分析报告|
|趋势数据|事件传播趋势图|
|情感分布|情感比例图|
|平台分布|新闻社交平台占比|
|关键词|关键词词云展示|

---

# 4.3 智能问答模块（qa.json）

功能：

通过接入大语言模型，实现用户针对指定舆情事件进行提问。


主要接口：

```text
POST /api/events/{event_id}/qa

GET /api/qa/history/{conversation_id}
```


支持：

- 当前事件问答
- 多轮对话
- 聊天记录保存


问答流程：

```text
用户输入问题

        ↓

C 后端接收请求

        ↓

调用大模型

        ↓

保存聊天记录

        ↓

返回回答
```

---

# 4.4 舆情预测模块（prediction.json）

功能：

预测舆情事件当前生命周期阶段以及未来发展趋势。


主要接口：

```text
GET /api/events/{event_id}/lifecycle
```


生命周期阶段：

|字段|含义|
|-|-|
|latent|潜伏期|
|growth|成长期|
|peak|高潮期|
|decline|衰退期|


接口返回：

- 当前生命周期阶段
- 阶段预测概率
- 预测置信度
- 未来热度趋势

---

# 5. API 数据格式规范

所有接口统一采用 JSON 数据格式。

统一返回结构：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

字段说明：

|字段|说明|
|-|-|
|code|接口状态码|
|message|接口返回信息|
|data|业务数据内容|

---

# 6. 模块协作规范

## A → C

A 需要提供：

- 原始数据字段定义
- 数据存储结构
- 数据更新方式


例如：

```text
title
content
publish_time
source
platform
```

---

## B → C

B 需要提供：

- 算法输出字段
- 字段含义
- 更新频率


例如：

```text
heat

sentiment

stage

keywords

future_trend
```

---

## C → D

C 需要提供：

- API路径
- 请求参数
- 返回 JSON 格式
- 字段说明


D 根据 API 实现：

- 页面展示
- 数据可视化
- 用户交互

---

# 7. 当前版本说明

版本：

```text
API Version: 1.0
```

已实现设计：

- 用户登录与个人配置
- 热点事件展示
- 事件详情分析
- 趋势分析
- 情感分析
- 平台分布分析
- 高频关键词分析
- 大模型智能问答
- 舆情生命周期预测


暂未包含高级功能：

- 虚假文本检测
- 事件溯源与关键传播路径分析

后续可根据项目进度扩展。