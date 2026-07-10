# -*- coding: utf-8 -*-
"""
网络请求重试装饰器。

用于包装容易因网络抖动 / 429 限流 / 临时 5xx 而失败的请求函数，
带指数退避 + 抖动，避免：
  1. 一次限流就把整批候选丢掉
  2. 固定间隔重试导致的"重试风暴"（多个请求同时按同一节奏撞限流）

用法：
    from utils.retry import retry_with_backoff

    @retry_with_backoff(max_attempts=3, base_delay=2.0)
    def fetch(url):
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()

被装饰的函数在耗尽重试次数后仍然失败，会抛出最后一次的异常；
调用方原有的 try/except 逻辑不需要改动，只是失败前会自动多试几次。
"""
import functools
import random
import time

from utils.logger import get_logger

log = get_logger("retry")

# 遇到这些 HTTP 状态码值得重试（限流 / 服务端临时故障）
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _is_retryable_exception(exc: Exception) -> bool:
    """判断异常是否值得重试：超时、连接错误，或状态码在可重试集合内"""
    import requests

    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError):
        status = getattr(exc.response, "status_code", None)
        return status in _RETRYABLE_STATUS
    return False


def retry_with_backoff(max_attempts: int = 3,
                        base_delay: float = 2.0,
                        max_delay: float = 30.0,
                        retry_on: tuple = (Exception,),
                        only_retryable: bool = True):
    """
    指数退避重试装饰器。

    max_attempts   — 最多尝试次数（含首次），默认 3
    base_delay     — 首次重试等待秒数，之后每次翻倍
    max_delay      — 单次等待上限，避免退避到几分钟
    retry_on       — 触发重试的异常类型元组
    only_retryable — True 时只对"值得重试"的异常（超时/连接错误/429/5xx）重试，
                     其它异常直接抛出；False 时对 retry_on 内所有异常都重试
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exc = e
                    if only_retryable and not _is_retryable_exception(e):
                        raise
                    if attempt == max_attempts:
                        break
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    delay += random.uniform(0, delay * 0.3)  # 抖动，防止重试风暴
                    log.warning(
                        "%s 第 %d/%d 次失败: %s，%.1fs 后重试",
                        func.__name__, attempt, max_attempts, e, delay,
                    )
                    time.sleep(delay)
            log.error("%s 重试 %d 次后仍失败: %s", func.__name__, max_attempts, last_exc)
            raise last_exc
        return wrapper
    return decorator


def request_with_retry(fn, *args, max_attempts: int = 3,
                       base_delay: float = 2.0,
                       max_delay: float = 30.0, **kwargs):
    """Call fn(*args, **kwargs) with exponential-backoff retry.

    Retries on timeouts, connection errors, and HTTP 429/5xx status codes.
    Returns the result of the first successful call, or raises the last exception
    if all attempts fail — same retry policy as L{retry_with_backoff}.

    Usage:
        resp = request_with_retry(session.get, url, params=params, timeout=15)
        resp = request_with_retry(session.post, url, json=payload, timeout=10)
    """
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if not _is_retryable_exception(e):
                raise
            if attempt == max_attempts:
                break
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay += random.uniform(0, delay * 0.3)
            log.warning(
                "%s attempt %d/%d failed: %s, retry in %.1fs",
                getattr(fn, "__name__", str(fn)),
                attempt, max_attempts, e, delay,
            )
            time.sleep(delay)
    log.error("%s failed after %d attempts: %s",
              getattr(fn, "__name__", str(fn)), max_attempts, last_exc)
    raise last_exc
