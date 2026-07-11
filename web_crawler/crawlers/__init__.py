# -*- coding: utf-8 -*-
"""
爬虫注册表。

加新平台时两步：
  1. 在 crawlers/ 下新建模块，类上加 @register("平台名")
  2. 确保模块被 import（在 crawlers/__init__.py 或 orchestrator.py 中 import）
"""

from typing import Any

_REGISTRY: dict[str, type] = {}


def register(name: str):
    """装饰器：将爬虫类注册到全局注册表"""
    def wrapper(cls):
        _REGISTRY[name] = cls
        return cls
    return wrapper


def get_crawler(name: str, **kwargs) -> Any:
    """根据名称获取爬虫实例"""
    cls = _REGISTRY.get(name)
    if cls is None:
        raise KeyError(
            f"未知平台: {name}，已注册: {list(_REGISTRY.keys())}"
        )
    return cls(**kwargs)


def list_platforms() -> list[str]:
    """列出所有已注册的平台名"""
    return list(_REGISTRY.keys())


# 确保所有爬虫模块在导入时完成注册
from crawlers import sina  # noqa: F401
from crawlers import weibo  # noqa: F401
from crawlers import zhihu  # noqa: F401
from crawlers import thepaper  # noqa: F401