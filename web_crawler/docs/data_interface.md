 # 爬虫 + 数据清洗数据接口说明
 
 ## 模块作用
 
 结构化后的干净文本数据，分别写入 `raw_documents`（新闻/帖子）和 `raw_comments`（评论）两张表，供算法模块做 NLP 分析和事件聚合。
 
 ## 数据流总览
 
 ```
 scheduler (APScheduler 定时触发)
   │
   ▼
 orchestrator.run(keyword, platform)     ← 支持单关键词/单平台或全配置批量
   │
   ├─ 1. crawler.search_multi_page()     ← 搜索候选列表（标题 + URL + 元信息）
   │
   ├─ 2. check_url()                     ← 第一阶段去重（URL 精确匹配，避免无用 HTTP 请求）
   │
   ├─ 3. extractor.extract(url)          ← 下载页面 / 调 API，提取结构化正文
   │
   ├─ 4. cleaner.build_document()        ← 噪音过滤、HTML 实体还原、boilerplate 移除
   │
   ├─ 5. check_content()                 ← 第二阶段去重（SimHash 64bit，海明距离 ≤ 3）
   │
   ├─ 6. storage.save_document()         ← 写入 raw_documents 表，clean_status='raw'
   │
   └─ 7. [社交平台] crawler.fetch_comments() → save_comment() → raw_comments 表
                         │
                         ▼
                   算法模块轮询或事件触发
                         │
                         ▼
                   后端模块读取已打标数据
 ```
 
 ## 文件结构与职责
 
 ```
 crawlers/
 ├── __init__.py         # 注册表: register() / get_crawler() / list_platforms()
 ├── sina.py             # @register("sina"): 新浪新闻搜索（通用新闻搜索引擎）
 ├── zhihu.py            # @register("zhihu"): 知乎搜索 + 评论拉取（社交平台）
 └── weibo.py            # @register("weibo"): 微博搜索 + 评论拉取（社交平台）
 
 pipeline/
 ├── __init__.py
 ├── extractor.py        # 正文抽取
 │   ├── NewspaperExtractor    # type="news"   → newspaper3k，适用于新闻网站
 │   ├── ReadabilityExtractor  # type="social" → readability-lxml，适用于社交页面
 │   └── WeiboExtractor        # type="weibo"  → weibo.com/ajax/statuses/show API
 └── cleaner.py          # 手写去噪脚本 + 标准文档构建
 
 utils/                  #一些用于反爬的策略
 ├── __init__.py
 ├── config.py           # 配置加载与校验（load_config / validate_config）
 ├── logger.py           # 统一日志配置（RotatingFileHandler + 控制台）
 └── retry.py            # 网络请求重试装饰器（指数退避 + 抖动）
 
 storage.py              # 数据库引擎、两阶段去重、文档/评论入库
 orchestrator.py         # 统一编排入口
 scheduler.py            # APScheduler 定时调度
 crawl_config.json       # 爬虫配置 + 关键词列表 + 调度参数
 ```
 
 ### 当前已对接的平台
 
 | 平台 | 注册名 | 注册类 | 抽取策略 |
 |------|--------|--------|---------|
 | 新浪新闻 | `sina` | SinaCrawler | `news` (NewspaperExtractor) |
 | 微博 | `weibo` | WeiboCrawler | `weibo` (WeiboExtractor) |
 | 知乎 | `zhihu` | ZhihuCrawler | `zhihu` (ZhihuExtractor) |
 
 ## 数据库表设计 — 模块产出
 
 ### 表 1: raw_documents（新闻/帖子数据）
 
 | 字段 | 类型 | 约束 | 说明 | 写入方  |
 |------|------|------|------|--------|
 | doc_id | VARCHAR(64) | PK | 确定性主键：`{平台码}{发布时间YYYYMMDDHHmmss}{url_md5[:8]}`，如 `WB20260709143025a1b2c3d4` | **A**  |
 | source_platform | VARCHAR(20) | NOT NULL | 来源平台 display_name（如"新浪新闻"） | **A**  |
 | source_url | VARCHAR(500) | DEFAULT NULL | 原文 URL（URL 精确去重依据） | **A**  |
 | title | VARCHAR(500) | DEFAULT NULL | 文章标题（微博取正文前 50 字） | **A**  |
 | content | TEXT | NOT NULL | **清洗后的正文**（已去除 boilerplate、零宽字符） | **A** | **B（核心输入）** |
 | author | VARCHAR(100) | DEFAULT NULL | 作者 / 媒体来源 / 发帖人昵称 | **A**  |
 | publish_time | DATETIME | DEFAULT NULL | 发布时间（ctime → publish_date → 当前时间 三级兜底） | **A**  |
 | crawl_time | DATETIME | NOT NULL | 爬虫抓取时间 | **A** |
 | content_hash | VARCHAR(64) | DEFAULT NULL | SimHash 64bit 指纹（给 C 做近似去重和聚合用） | **A** |
 | verification_type | VARCHAR(50) | DEFAULT NULL | 信源认证类型 | **A** |
 | sentiment_label | VARCHAR(10) | DEFAULT NULL | 情感标签：正面/负面/中性（C 回填） | **B** |
 | sentiment_score | FLOAT | DEFAULT NULL | 情感置信度 [0, 1]（C 回填） | **B** |
 | keywords | TEXT | DEFAULT NULL | JSON 数组或逗号分隔关键词（C 回填） | **B** |
 | event_id | INT | DEFAULT NULL | 所属事件 ID，外键 → events 表（C 聚类后回填） | **B** |
 | clean_status | VARCHAR(20) | NOT NULL DEFAULT 'raw' | 数据状态 raw → enriched → dirty | **A 初始写入** |
 
 索引建议：
 ```sql
 CREATE INDEX idx_raw_platform     ON raw_documents(source_platform);
 CREATE INDEX idx_raw_publish_time ON raw_documents(publish_time);
 CREATE INDEX idx_raw_event        ON raw_documents(event_id);
 CREATE INDEX idx_raw_clean_status ON raw_documents(clean_status);
 ```
 
 ### 表 2: raw_comments（社交平台评论数据）
 
 | 字段 | 类型 | 约束 | 说明 | 写入方 |
 |------|------|------|------|--------|
 | comment_id | VARCHAR(64) | PK | 微博接口返回的评论 ID 字符串 | **A** |
 | source_platform | VARCHAR(20) | NOT NULL | 来源平台 display_name | **A**  |
 | parent_post_id | VARCHAR(64) | NOT NULL, FK→raw_documents.doc_id | **所属帖子的 doc_id**（关键关联字段） | **A** |
 | source_url | VARCHAR(500) | DEFAULT NULL | 评论页面 URL（去重依据） | **A** |
 | content | TEXT | NOT NULL | 清洗后的评论正文 | **A** | 
 | author | VARCHAR(100) | DEFAULT NULL | 评论者昵称 | **A** |
 | user_id | VARCHAR(64) | DEFAULT NULL | 评论者 UID | **A** |
 | commenter_ip | VARCHAR(45) | DEFAULT NULL | 评论者 IP 地址 | **A** | 
 | likes_count | INT | DEFAULT 0 | 点赞数 | **A** | 
 | publish_time | DATETIME | DEFAULT NULL | 评论发布时间 | **A** |
 | crawl_time | DATETIME | NOT NULL | 抓取时间 | **A** | 
 | content_hash | VARCHAR(64) | DEFAULT NULL | SimHash 64bit 指纹 | **A** | 
 | duplicate_count | INT | DEFAULT 1 | 相同或近似评论累计出现次数 | **A** | 
 | sentiment_label | VARCHAR(10) | DEFAULT NULL | 情感标签（B回填） | **B** | 
 | sentiment_score | FLOAT | DEFAULT NULL | 情感置信度（B回填） | **B** |
 | keywords | TEXT | DEFAULT NULL | 关键词（B回填） | **B** |
 | clean_status | VARCHAR(20) | NOT NULL DEFAULT 'raw' | 数据状态 | **A初始写入** |

 > **content_hash 说明**：SimHash(clean_content).value 的字符串形式（64 位整数转 str）。算法做事件聚合时可直接比对 SimHash 距离，无需重新计算全文指纹。
 
 
> **verification_type 说明**：由 A 阶段爬虫根据各平台原始认证信息（如微博 verified_type）归一化后写入，五档枚举，跨平台统一：

| 枚举值 | 含义 |
|------|------|
| `官方平台` | 业务白名单权威媒体/平台官方账号（如人民日报、央视新闻、新华社） |
| `头部认证个人` | 平台按影响力/内容质量评定的高权重个人（如微博红V/金V） |
| `认证个人` | 基础个人身份/资质认证（如微博黄V） |
| `认证机构` | 机构类账号，不区分企业/政府/媒体/校园等子类型（如微博蓝V） |
| `普通用户` | 无认证，或来源不适用认证概念（如新浪新闻这类新闻网站文章） | 
> **clean_status 说明**:

| 状态 | 含义 |
|------|------|
| `raw` | A 刚写入，尚未经过 NLP 处理 |
| `enriched` | B 已完成情感/关键词/事件打标 |
| `dirty` | 数据异常，被流水线跳过 |

 
 ## 两阶段去重策略
 
 | 阶段 | 位置 | 方法 | 阈值 | 说明 |
 |------|------|------|------|------|
 | 1. URL 精确去重 | storage.check_url() | SELECT 1 WHERE source_url = :url | 精确匹配 | 正文下载前调用，避免无用 HTTP |
 | 2. 内容近似去重 | storage.check_content() | SimHash 64bit 海明距离 | ≤ 3 | 正文提取后调用，检测跨 URL 重复 |
 
 算法在事件聚合时可利用 `content_hash` 做匹配将跨平台报道聚合同一事件。
 
 ## 配置方式
 
 ### 数据库+cookie连接
 通过 `.env` 文件管理（已加入 `.gitignore`）：
 ```
 DB_USER=root
 DB_PASSWORD=your_password
 DB_HOST=localhost
 DB_PORT=3306
 DB_DATABASE=public_opinion_system

 SINA_COOKIE=your_sina_cookie_here
 WEIBO_COOKIE=your_weibo_cookie_here
 ZHIHU_COOKIE=your_zhihu_cookie_here
 # 多账号轮换（可选）
 # WEIBO_COOKIE_2=your_second_weibo_cookie_here
 # ZHIHU_COOKIE_2=your_second_zhihu_cookie_here
 ```
 
 ### crawl_config.json 结构
 ```json
 {
   "crawler": {
     "sina": {
       "enabled": true,
       "keywords": ["广西洪灾", "广西暴雨"],
       "max_articles_per_keyword": 30,
       "request_interval": 1.5
     },
     "weibo": {
       "enabled": true,
       "keywords": ["广西洪灾", "广西暴雨"],
       "max_articles_per_keyword": 20,
       "max_comments_per_article": 25,
       "request_interval": 1.5
     }
   },
   "scheduler": {
     "interval_hours": 2,
     "run_at_start": true
   }
 }
 ```
 
 ## 启动方式
 ```bash
 pip install -r requirements.txt
 cp .env.example .env
 mysql -u root -p public_opinion_system < docs/init.sql
 python orchestrator.py "关键词" --platform sina --dry-run
 python orchestrator.py "关键词" --platform sina
 python orchestrator.py --config
 python scheduler.py
 python scheduler.py --run-once
 ```
 
 ## 新平台接入指南
 1. 在 crawlers/ 下新建模块，类上加 @register("平台名")
 2. 定义 display_name、extractor_type（news/social/weibo）
 3. 实现 search_multi_page(keyword, max_pages) → 候选列表
 4. 可选：实现 fetch_comments() 支持评论爬取
 5. 可选：在 pipeline/extractor.py 新增提取策略并注册到 EXTRACTOR_MAP
 6. 在 cleaner.py 的 BOILERPLATE_PATTERNS 追加平台 boilerplate
 7. 在 crawl_config.json 新增平台配置
 



