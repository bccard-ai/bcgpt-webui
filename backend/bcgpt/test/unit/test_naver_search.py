import logging

import pytest

from bcgpt.retrieval.web import naver


def test_search_naver_raises_single_summary_when_all_endpoints_fail(monkeypatch):
    def fail_endpoint(*args, **kwargs):
        raise RuntimeError("certificate verify failed")

    monkeypatch.setattr(naver, "_search_single_endpoint", fail_endpoint)

    with pytest.raises(RuntimeError) as exc_info:
        naver.search_naver(
            "client-id",
            "client-secret",
            "query",
            3,
            endpoints="webkr,news,blog",
        )

    message = str(exc_info.value)
    assert "Naver search failed for all endpoints" in message
    assert "webkr" in message
    assert "news" in message
    assert "blog" in message
    assert message.count("certificate verify failed") == 1


def test_search_naver_warns_once_and_keeps_partial_results(monkeypatch, caplog):
    def search_endpoint(client_id, client_secret, endpoint, query, display, sort="sim"):
        if endpoint == "news":
            raise RuntimeError("news endpoint failed")

        return [
            {
                "link": f"https://{endpoint}.example.com/result",
                "title": "<b>Title</b>",
                "description": "Description",
            }
        ]

    monkeypatch.setattr(naver, "_search_single_endpoint", search_endpoint)
    caplog.set_level(logging.WARNING, logger=naver.log.name)

    results = naver.search_naver(
        "client-id",
        "client-secret",
        "query",
        3,
        endpoints="webkr,news",
    )

    assert len(results) == 1
    assert results[0].title == "Title"
    assert "Naver search failed on 1/2 endpoints" in caplog.text
    assert caplog.text.count("news endpoint failed") == 1


def test_search_naver_raises_when_endpoint_failures_leave_no_results(monkeypatch):
    def search_endpoint(client_id, client_secret, endpoint, query, display, sort="sim"):
        if endpoint == "news":
            raise RuntimeError("news endpoint failed")

        return []

    monkeypatch.setattr(naver, "_search_single_endpoint", search_endpoint)

    with pytest.raises(RuntimeError) as exc_info:
        naver.search_naver(
            "client-id",
            "client-secret",
            "query",
            3,
            endpoints="webkr,news",
        )

    message = str(exc_info.value)
    assert "Naver search returned no results after endpoint failures" in message
    assert message.count("news endpoint failed") == 1
