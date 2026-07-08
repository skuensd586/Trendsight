"""Fake raw records for running the M1 pipeline end-to-end without a live crawler.

Three synthetic events, each with several reports across different sources/platforms/
times, including one deliberate near-duplicate pair per event (the same wire story
reprinted by two outlets) to exercise SimHash dedup. `event_id` stands in for the
event clustering step (M2) — real crawler output won't have it pre-assigned.
"""
from __future__ import annotations

RAW_RECORDS: list[dict] = [
    # --- evt-flood: 某市暴雨致地铁站进水 (2026-07-05 -> 07-06) ---
    {
        "doc_id": "flood-1", "event_id": "evt-flood",
        "title": "某市突降暴雨部分地铁站出现积水",
        "content": "某市今日凌晨突降暴雨，部分地铁站点出现积水，地铁公司已启动应急预案，"
                   "安排工作人员现场排查，暂未收到人员伤亡报告。",
        "publish_time": "2026-07-05 08:10:00", "source": "本地都市报", "platform": "微博",
        "url": "https://example.com/flood-1", "author": "记者甲",
    },
    {
        "doc_id": "flood-2", "event_id": "evt-flood",
        "title": "暴雨致地铁站进水 现场救援持续进行",
        "content": "受强降雨影响，某市多个地铁站出现进水情况，救援人员和市政工作人员紧急赶赴"
                   "现场处置，部分乘客对地铁公司应对速度表示不满，也有网友对救援人员的辛苦表示感谢。",
        "publish_time": "2026-07-05 10:30:00", "source": "新华社", "platform": "官方网站",
        "url": "https://example.com/flood-2", "author": "记者乙",
    },
    {
        # near-duplicate of flood-2: same wire story reprinted with minor edits
        "doc_id": "flood-3", "event_id": "evt-flood",
        "title": "暴雨致地铁站进水 救援持续进行中",
        "content": "受强降雨影响，某市多个地铁站出现进水情况，救援人员和市政工作人员紧急赶赴"
                   "现场处置，不少乘客对地铁公司应对速度表示不满，也有网友对救援人员的辛苦表示感谢。"
                   "据悉当前抢险工作仍在进行。",
        "publish_time": "2026-07-05 10:35:00", "source": "地方晚报", "platform": "新闻客户端",
        "url": "https://example.com/flood-3", "author": "记者丙",
    },
    {
        "doc_id": "flood-4", "event_id": "evt-flood",
        "title": "网友质疑地铁站防汛设施不足",
        "content": "针对此次暴雨进水事件，大量网友在社交平台质疑地铁站防汛设施建设不足，"
                   "纷纷留言批评相关部门监管不到位，要求彻查此次事故原因。",
        "publish_time": "2026-07-05 12:00:00", "source": "本地都市报", "platform": "微博",
        "url": "https://example.com/flood-4", "author": "记者甲",
    },
    {
        "doc_id": "flood-5", "event_id": "evt-flood",
        "title": "地铁公司致歉：将全面排查防汛隐患",
        "content": "地铁公司发布致歉声明，表示将对全线地铁站防汛设施进行全面排查整改，"
                   "并对此次事件给市民造成的不便表示歉意，部分网友对整改态度表示认可。",
        "publish_time": "2026-07-05 12:30:00", "source": "都市晨报", "platform": "微博",
        "url": "https://example.com/flood-5", "author": "记者丁",
    },
    {
        "doc_id": "flood-6", "event_id": "evt-flood",
        "title": "积水已基本消退 地铁恢复部分运营",
        "content": "截至今日下午，此次暴雨导致的地铁站积水已基本消退，涉事线路已恢复部分运营，"
                   "现场秩序井然，多数乘客对地铁公司的处置效率表示满意。",
        "publish_time": "2026-07-05 15:00:00", "source": "地方晚报", "platform": "新闻客户端",
        "url": "https://example.com/flood-6", "author": "记者丙",
    },
    {
        "doc_id": "flood-7", "event_id": "evt-flood",
        "title": "地铁防汛整改方案公布 网友纷纷点赞",
        "content": "针对此前暴雨进水事件，地铁公司正式公布防汛整改方案，承诺加大设施投入，"
                   "网友对此次整改方案纷纷点赞，认为体现了积极负责的态度。",
        "publish_time": "2026-07-06 08:00:00", "source": "新华社", "platform": "官方网站",
        "url": "https://example.com/flood-7", "author": "记者乙",
    },
    {
        "doc_id": "flood-8", "event_id": "evt-flood",
        "title": "专家解读：城市内涝为何频发",
        "content": "有城市规划专家对此次事件进行解读，分析城市排水系统建设滞后等深层原因，"
                   "呼吁加大基础设施投入以应对极端天气。",
        "publish_time": "2026-07-06 09:00:00", "source": "都市晨报", "platform": "微博",
        "url": "https://example.com/flood-8", "author": "记者丁",
    },
    # --- evt-phone: 某品牌新旗舰手机发布 (2026-07-06) ---
    {
        "doc_id": "phone-1", "event_id": "evt-phone",
        "title": "某品牌发布新款旗舰手机",
        "content": "某品牌今日正式发布新款旗舰手机，主打影像和续航升级，现场观众反响热烈，"
                   "不少网友表示非常喜欢新配色。",
        "publish_time": "2026-07-06 09:00:00", "source": "科技媒体A", "platform": "官网",
        "url": "https://example.com/phone-1", "author": "记者戊",
    },
    {
        # near-duplicate of phone-1: another outlet's recap of the same press event
        "doc_id": "phone-2", "event_id": "evt-phone",
        "title": "某品牌正式发布新款旗舰手机",
        "content": "某品牌今日正式发布新款旗舰手机，主打影像和续航能力升级，现场观众反响热烈，"
                   "许多网友表示非常喜欢新配色和外观设计。",
        "publish_time": "2026-07-06 09:05:00", "source": "科技媒体B", "platform": "新闻客户端",
        "url": "https://example.com/phone-2", "author": "记者己",
    },
    {
        "doc_id": "phone-3", "event_id": "evt-phone",
        "title": "上手体验：新机做工获好评",
        "content": "多家媒体率先上手体验新机，普遍给予好评，认为做工用料扎实，性价比获得认可，"
                   "但也有博主质疑摄像头凸起过高影响手感。",
        "publish_time": "2026-07-06 11:00:00", "source": "数码测评号", "platform": "微博",
        "url": "https://example.com/phone-3", "author": "记者庚",
    },
    {
        "doc_id": "phone-4", "event_id": "evt-phone",
        "title": "新机开售即售罄 厂商回应产能问题",
        "content": "新机开售后迅速售罄，厂商回应称将加快产能爬坡，尽快满足消费者需求，"
                   "网友对首销火爆表示支持。",
        "publish_time": "2026-07-06 13:00:00", "source": "科技媒体A", "platform": "官网",
        "url": "https://example.com/phone-4", "author": "记者戊",
    },
    {
        "doc_id": "phone-5", "event_id": "evt-phone",
        "title": "部分用户反馈发热问题 厂商称将优化",
        "content": "有部分用户反馈手机在高负载场景下存在发热现象，对使用体验表示担忧，"
                   "厂商回应称将通过后续系统更新优化散热表现。",
        "publish_time": "2026-07-06 15:00:00", "source": "数码测评号", "platform": "微博",
        "url": "https://example.com/phone-5", "author": "记者庚",
    },
    # --- evt-canteen: 某高校食堂食品安全问题 (2026-07-01 -> 07-03, older -> lower hotness) ---
    {
        "doc_id": "canteen-1", "event_id": "evt-canteen",
        "title": "学生反映食堂饭菜疑似变质",
        "content": "有学生在校园论坛反映食堂部分饭菜存在异味，怀疑食材变质，对此事表示强烈不满，"
                   "要求学校尽快调查处理。",
        "publish_time": "2026-07-01 09:00:00", "source": "校园论坛", "platform": "论坛",
        "url": "https://example.com/canteen-1", "author": "学生甲",
    },
    {
        "doc_id": "canteen-2", "event_id": "evt-canteen",
        "title": "高校食堂食品安全问题引发关注",
        "content": "此事经媒体报道后引发广泛关注，多名学生和家长对食堂食品安全表示担忧，"
                   "呼吁监管部门介入调查。",
        "publish_time": "2026-07-01 14:00:00", "source": "都市晨报", "platform": "微博",
        "url": "https://example.com/canteen-2", "author": "记者丁",
    },
    {
        "doc_id": "canteen-3", "event_id": "evt-canteen",
        "title": "监管部门介入调查涉事食堂",
        "content": "市场监管部门已介入调查涉事高校食堂，对相关食材进行抽检，"
                   "如发现违规行为将依法处理，调查结果将及时公布。",
        "publish_time": "2026-07-02 10:00:00", "source": "市场监管发布", "platform": "官方网站",
        "url": "https://example.com/canteen-3", "author": "记者辛",
    },
    {
        "doc_id": "canteen-4", "event_id": "evt-canteen",
        "title": "校方通报整改情况 学生满意度提升",
        "content": "校方发布通报称已对涉事食堂进行整改并加强日常检查，多数学生对整改效果表示满意，"
                   "认为食堂环境有明显改善。",
        "publish_time": "2026-07-03 09:00:00", "source": "校园论坛", "platform": "论坛",
        "url": "https://example.com/canteen-4", "author": "学生乙",
    },
]
