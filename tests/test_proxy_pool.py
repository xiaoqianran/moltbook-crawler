"""Tests for proxy pool loader."""

from __future__ import annotations

from crawlers.proxy_pool import ProxyEntry, ProxyPool, load_pool_from_results


def test_load_pool_from_results(proxy_results_dir):
    pool = load_pool_from_results(proxy_results_dir, source_ids=["test_http"], max_proxies=10)
    assert len(pool) == 2
    url = pool.acquire()
    assert url and url.startswith("http://")


def test_proxy_pool_report():
    pool = ProxyPool([ProxyEntry(url="http://1.2.3.4:8080", source_id="t")])
    pool.report("http://1.2.3.4:8080", success=False)
    pool.report("http://1.2.3.4:8080", success=False)
    assert pool.entries[0].failures == 2