# -*- coding: utf-8 -*-
"""
统一日志配置。
替代散落各处的 print()，提供:
  - 控制台输出（保留开发时的直观体验）
  - 按大小轮转的文件日志（logs/crawler.log），便于长期运行后排查问题
  - 统一的时间戳 + 级别格式

用法：
    from utils.logger import get_logger
    log = get_logger(__name__)
    log.info("开始爬取 %s", keyword)
    log.warning("cookie 可能已过期")
    log.error("请求失败: %s", e)
"""
import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "crawler.log")
_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root():
    """只在首次调用时配置根 handler，避免重复添加导致日志重复打印"""
    global _configured
    if _configured:
        return
    os.makedirs(_LOG_DIR, exist_ok=True)

    root = logging.getLogger("crawler")
    root.setLevel(logging.INFO)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # 单文件最大 10MB，保留最近 5 份，避免长期运行把磁盘写满
    file_handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    root.propagate = False
    _configured = True


def get_logger(name: str = "crawler") -> logging.Logger:
    """获取一个子 logger，日志会同时写入控制台和 logs/crawler.log"""
    _configure_root()
    if not name.startswith("crawler"):
        name = f"crawler.{name}"
    return logging.getLogger(name)


setup_logging = _configure_root
