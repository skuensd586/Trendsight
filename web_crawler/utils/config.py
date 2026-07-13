# -*- coding: utf-8 -*-
"""
配置加载与校验。
统一 orchestrator.py / scheduler.py 的配置读取逻辑，
并在加载时做基本 schema 校验，配置写错时给出清晰报错而不是
运行到一半才抛 KeyError。
"""
import json

from utils.logger import get_logger

log = get_logger("config")

# 每页搜索接口大致能返回的有效候选数（经验值，来自 sina/weibo 搜索接口的实测翻页情况）。
# orchestrator 用它估算"要拿到 limit 条候选，大概需要翻多少页"。
CANDIDATES_PER_PAGE = 15


class ConfigError(ValueError):
    """配置文件格式或内容不合法"""


def load_config(path: str) -> dict:
    """加载并校验 crawl_config.json，格式错误时抛出 ConfigError 而非在使用处才报错"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"配置文件不存在: {path}")
    except json.JSONDecodeError as e:
        raise ConfigError(f"配置文件 JSON 格式错误: {path}: {e}")

    _validate(cfg, path)
    return cfg


def _validate(cfg: dict, path: str):
    if "crawler" not in cfg:
        raise ConfigError(f"{path} 缺少顶层字段 'crawler'")
    if not isinstance(cfg["crawler"], dict) or not cfg["crawler"]:
        raise ConfigError(f"{path} 的 'crawler' 字段必须是非空对象")

    for platform, pc in cfg["crawler"].items():
        if not isinstance(pc, dict):
            raise ConfigError(f"{path}: crawler.{platform} 必须是对象")
        if pc.get("enabled", True) and "keywords" not in pc:
            raise ConfigError(f"{path}: crawler.{platform} 已启用但缺少 'keywords' 字段")
        if "keywords" in pc:
            if not isinstance(pc["keywords"], list) or not all(
                isinstance(k, str) and k.strip() for k in pc["keywords"]
            ):
                raise ConfigError(f"{path}: crawler.{platform}.keywords 必须是非空字符串列表")
        for numeric_field in ("max_articles_per_keyword", "max_comments_per_article", "request_interval"):
            if numeric_field in pc and not isinstance(pc[numeric_field], (int, float)):
                raise ConfigError(f"{path}: crawler.{platform}.{numeric_field} 必须是数字")

    scheduler_cfg = cfg.get("scheduler", {})
    if scheduler_cfg and not isinstance(scheduler_cfg, dict):
        raise ConfigError(f"{path}: 'scheduler' 字段必须是对象")
    if "interval_hours" in scheduler_cfg and scheduler_cfg["interval_hours"] <= 0:
        raise ConfigError(f"{path}: scheduler.interval_hours 必须大于 0")

    log.info("配置校验通过: %s", path)


def validate_config(cfg: dict) -> None:
    """校验已加载的配置字典（不从文件读取），不合法时抛出 ConfigError"""
    _validate(cfg, "(loaded_config)")


def enabled_platforms(cfg: dict) -> list[str]:
    """返回已启用且配置了 keywords 的平台名列表"""
    return [
        name for name, pc in cfg["crawler"].items()
        if isinstance(pc, dict) and pc.get("enabled", True) and "keywords" in pc
    ]
