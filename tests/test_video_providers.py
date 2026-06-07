"""
Unit tests for the pluggable video-provider layer and the pipeline's
provider selection + cost-estimation features. No network.
"""

from __future__ import annotations

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import image_to_video_pipeline as i2v  # noqa: E402
import video_providers as vp  # noqa: E402


# ─── Fakes (mirrors the i2v test harness) ─────────────────────────────────────


class FakeResp:
    def __init__(self, status=200, json_body=None, headers=None):
        self.status = status
        self._json = json_body or {}
        self.headers = headers or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self):
        return self._json


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        return self._responses.pop(0)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    async def _instant(_s):
        return None

    monkeypatch.setattr(i2v.asyncio, "sleep", _instant)


# ─── Registry ─────────────────────────────────────────────────────────────────


def test_get_provider_returns_instances():
    assert isinstance(vp.get_provider("kling"), vp.KlingProvider)
    assert isinstance(
        vp.get_provider("GoEnhance"), vp.GoEnhanceProvider
    )  # case-insensitive


def test_get_provider_unknown_raises():
    with pytest.raises(ValueError, match="Unknown provider"):
        vp.get_provider("nope")


# ─── Kling provider ───────────────────────────────────────────────────────────


def test_kling_build_submit_request_defaults_and_overrides():
    k = vp.KlingProvider()
    url, payload = k.build_submit_request({"base64": "ABC"}, {})
    assert url == k.SUBMIT_URL
    assert payload["model_name"] == "kling-v3"
    assert payload["image"] == "ABC"
    assert payload["mode"] == "pro" and payload["duration"] == 10

    _, payload2 = k.build_submit_request(
        {"base64": "ABC"}, {"mode": "std", "duration": 5, "prompt": "p"}
    )
    assert (
        payload2["mode"] == "std"
        and payload2["duration"] == 5
        and payload2["prompt"] == "p"
    )


def test_kling_parse_submit_response():
    k = vp.KlingProvider()
    assert k.parse_submit_response(200, {"data": {"task_id": "T1"}}) == "T1"
    with pytest.raises(RuntimeError, match="Submit error 403"):
        k.parse_submit_response(403, {"message": "no"})


def test_kling_parse_status_transitions():
    k = vp.KlingProvider()
    succ = k.parse_status(
        {
            "data": {
                "task_status": "succeed",
                "task_result": {"videos": [{"url": "http://v/c.mp4"}]},
            }
        }
    )
    assert succ.state == "succeed" and succ.video_url == "http://v/c.mp4"

    fail = k.parse_status(
        {"data": {"task_status": "failed", "task_status_msg": "boom"}}
    )
    assert fail.state == "failed" and fail.message == "boom"

    pend = k.parse_status({"data": {"task_status": "processing"}})
    assert pend.state == "pending"


def test_kling_estimate_cost_modes():
    k = vp.KlingProvider()
    pro = k.estimate_cost({"mode": "pro", "duration": 10}, 4)
    assert pro.provider == "kling" and pro.num_clips == 4
    assert pro.per_clip == round(10 * k.PRICE_PER_SECOND["pro"], 4)
    assert pro.total == round(pro.per_clip * 4, 2)

    std = k.estimate_cost({"mode": "std", "duration": 5}, 1)
    assert std.per_clip < pro.per_clip  # std cheaper than pro


# ─── GoEnhance provider ───────────────────────────────────────────────────────


def test_goenhance_build_and_parse():
    g = vp.GoEnhanceProvider()
    url, payload = g.build_submit_request({"base64": "ZZ"}, {"duration": 8})
    assert url == g.SUBMIT_URL
    assert payload["image_base64"] == "ZZ" and payload["duration"] == 8

    assert g.parse_submit_response(200, {"data": {"task_id": "G1"}}) == "G1"
    assert g.parse_submit_response(200, {"id": "G2"}) == "G2"  # top-level fallback
    with pytest.raises(RuntimeError, match="No task_id"):
        g.parse_submit_response(200, {"data": {}})
    with pytest.raises(RuntimeError, match="Submit error 500"):
        g.parse_submit_response(500, {})


def test_goenhance_parse_status():
    g = vp.GoEnhanceProvider()
    assert (
        g.parse_status({"data": {"status": "completed", "video_url": "u"}}).state
        == "succeed"
    )
    assert (
        g.parse_status({"data": {"status": "error", "message": "x"}}).state == "failed"
    )
    assert g.parse_status({"data": {"status": "processing"}}).state == "pending"


def test_cost_estimate_to_dict():
    est = vp.KlingProvider().estimate_cost({"duration": 10}, 2)
    d = est.to_dict()
    assert d["provider"] == "kling" and d["num_clips"] == 2 and "total" in d


# ─── Pipeline integration: provider selection + cost ──────────────────────────


def test_estimate_batch_cost_uses_active_provider(monkeypatch):
    monkeypatch.setattr(i2v, "ACTIVE_PROVIDER_NAME", "kling")
    est = i2v.estimate_batch_cost([{}, {}, {}], {"duration": 10, "mode": "pro"})
    assert est["provider"] == "kling" and est["num_clips"] == 3


def test_submit_job_routes_to_selected_provider(monkeypatch):
    monkeypatch.setattr(i2v, "ACTIVE_PROVIDER_NAME", "goenhance")
    session = FakeSession([FakeResp(200, {"data": {"task_id": "G9"}})])
    tid = asyncio.run(i2v.submit_job(session, {"base64": "ABC"}, {}))
    assert tid == "G9"
    # request was sent to the GoEnhance endpoint, not Kling's
    method, url = session.calls[0]
    assert url == vp.GoEnhanceProvider.SUBMIT_URL


def test_poll_routes_to_selected_provider(monkeypatch):
    monkeypatch.setattr(i2v, "ACTIVE_PROVIDER_NAME", "goenhance")
    session = FakeSession(
        [
            FakeResp(200, {"data": {"status": "processing"}}),
            FakeResp(
                200, {"data": {"status": "completed", "video_url": "http://v/c.mp4"}}
            ),
        ]
    )
    res = asyncio.run(i2v.poll_with_backoff(session, "G9"))
    assert res["status"] == "succeed" and res["video_url"] == "http://v/c.mp4"
    assert session.calls[0][1] == vp.GoEnhanceProvider.STATUS_URL.format(task_id="G9")
