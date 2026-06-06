"""
Unit tests for image_to_video_pipeline.

Self-contained: no live network, no pytest-asyncio plugin required (async
coroutines are driven via asyncio.run). aiohttp is faked at the session level.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys

import pytest
from PIL import Image

# Make the root-level script importable from tests/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import image_to_video_pipeline as i2v  # noqa: E402


# ─── Fakes ────────────────────────────────────────────────────────────────────

class FakeResp:
    """Minimal async-context-manager stand-in for an aiohttp response."""

    def __init__(self, status=200, json_body=None, headers=None, body=b""):
        self.status = status
        self._json = json_body if json_body is not None else {}
        self.headers = headers or {}
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def json(self):
        return self._json

    async def read(self):
        return self._body


class FakeSession:
    """
    Drives request() from a scripted queue of responses (or exceptions).
    .get() is used by the video download path and returns a fixed body.
    """

    def __init__(self, responses, download_body=b"VIDEO_BYTES"):
        self._responses = list(responses)
        self.calls = []
        self._download_body = download_body

    def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    def get(self, url, **kwargs):
        return FakeResp(status=200, body=self._download_body)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Make every backoff instant so tests run fast."""
    async def _instant(_seconds):
        return None

    monkeypatch.setattr(i2v.asyncio, "sleep", _instant)


def _make_image(path, size=(512, 910), color=(100, 80, 200), fmt="PNG"):
    Image.new("RGB", size, color).save(path, format=fmt)
    return path


# ─── Stage 1: validation ──────────────────────────────────────────────────────

def test_validate_accepts_good_image(tmp_path):
    p = _make_image(tmp_path / "good.png")
    rec = i2v.validate_and_encode(p)
    assert rec["filename"] == "good.png"
    assert rec["width_px"] == 512 and rec["height_px"] == 910
    assert rec["pil_format"] == "PNG"
    assert len(rec["checksum_sha256"]) == 64
    # base64 must be raw — no data-URI prefix
    assert not rec["base64"].startswith("data:")
    assert base64.b64decode(rec["base64"]) == p.read_bytes()


def test_validate_rejects_zero_byte(tmp_path):
    p = tmp_path / "empty.png"
    p.write_bytes(b"")
    with pytest.raises(ValueError, match="Zero-byte"):
        i2v.validate_and_encode(p)


def test_validate_rejects_oversize(tmp_path, monkeypatch):
    monkeypatch.setattr(i2v, "MAX_FILE_BYTES", 10)  # absurdly low ceiling
    p = _make_image(tmp_path / "big.png")
    with pytest.raises(ValueError, match="exceeds"):
        i2v.validate_and_encode(p)


def test_validate_rejects_small_dimensions(tmp_path):
    p = _make_image(tmp_path / "tiny.png", size=(100, 100))
    with pytest.raises(ValueError, match="below floor"):
        i2v.validate_and_encode(p)


def test_validate_rejects_extreme_aspect(tmp_path):
    # 2000x300 → aspect 6.67 > MAX_ASPECT_SKEW (4.0), both dims above floor
    p = _make_image(tmp_path / "wide.png", size=(2000, 300))
    with pytest.raises(ValueError, match="aspect ratio"):
        i2v.validate_and_encode(p)


def test_validate_rejects_corrupt(tmp_path):
    p = tmp_path / "notreally.png"
    p.write_bytes(b"this is not a png" * 50)
    with pytest.raises(ValueError):
        i2v.validate_and_encode(p)


def test_build_manifest_splits_valid_and_errors(tmp_path, monkeypatch):
    inp = tmp_path / "inputs"
    inp.mkdir()
    _make_image(inp / "ok.png")
    _make_image(inp / "small.png", size=(50, 50))
    monkeypatch.chdir(tmp_path)  # manifest/errors files land here
    manifests, errors = i2v.build_manifest(inp)
    assert len(manifests) == 1 and manifests[0]["filename"] == "ok.png"
    assert len(errors) == 1 and errors[0]["filename"] == "small.png"
    assert json.loads((tmp_path / "image_manifest.json").read_text())["total_valid"] == 1


# ─── Transient-HTTP retry ─────────────────────────────────────────────────────

def test_retry_delay_honors_numeric_retry_after():
    assert i2v._retry_delay(0, "7") == 7.0


def test_retry_delay_falls_back_on_bad_header():
    d = i2v._retry_delay(0, "Wed, 21 Oct 2099 07:28:00 GMT")
    assert d >= i2v.RETRY_BASE  # backoff path, not the header


def test_request_json_retries_then_succeeds():
    session = FakeSession([
        FakeResp(status=503),
        FakeResp(status=429, headers={"Retry-After": "0"}),
        FakeResp(status=200, json_body={"ok": True}),
    ])
    status, body = asyncio.run(i2v.request_json(session, "GET", "http://x"))
    assert status == 200 and body == {"ok": True}
    assert len(session.calls) == 3


def test_request_json_returns_non_transient_4xx_immediately():
    session = FakeSession([FakeResp(status=400, json_body={"err": "bad"})])
    status, body = asyncio.run(i2v.request_json(session, "POST", "http://x"))
    assert status == 400 and body == {"err": "bad"}
    assert len(session.calls) == 1


def test_request_json_retries_client_error():
    session = FakeSession([
        i2v.aiohttp.ClientError("boom"),
        FakeResp(status=200, json_body={"ok": 1}),
    ])
    status, _ = asyncio.run(i2v.request_json(session, "GET", "http://x"))
    assert status == 200 and len(session.calls) == 2


# ─── Submission ───────────────────────────────────────────────────────────────

def test_submit_job_returns_task_id():
    session = FakeSession([FakeResp(status=200, json_body={"data": {"task_id": "T123"}})])
    rec = {"base64": "AAAA"}
    tid = asyncio.run(i2v.submit_job(session, rec, {}))
    assert tid == "T123"


def test_submit_job_raises_on_error_status():
    session = FakeSession([FakeResp(status=403, json_body={"message": "forbidden"})])
    with pytest.raises(RuntimeError, match="Submit error 403"):
        asyncio.run(i2v.submit_job(session, {"base64": "AAAA"}, {}))


# ─── Polling ──────────────────────────────────────────────────────────────────

def test_poll_succeeds():
    session = FakeSession([
        FakeResp(json_body={"data": {"task_status": "processing"}}),
        FakeResp(json_body={"data": {
            "task_status": "succeed",
            "task_result": {"videos": [{"url": "http://v/clip.mp4"}]},
        }}),
    ])
    res = asyncio.run(i2v.poll_with_backoff(session, "T1"))
    assert res["status"] == "succeed" and res["video_url"] == "http://v/clip.mp4"


def test_poll_raises_on_failed():
    session = FakeSession([
        FakeResp(json_body={"data": {"task_status": "failed", "task_status_msg": "nope"}}),
    ])
    with pytest.raises(RuntimeError, match="Generation failed"):
        asyncio.run(i2v.poll_with_backoff(session, "T1"))


def test_poll_times_out(monkeypatch):
    monkeypatch.setattr(i2v, "MAX_POLLS", 3)
    session = FakeSession([
        FakeResp(json_body={"data": {"task_status": "processing"}}) for _ in range(3)
    ])
    with pytest.raises(TimeoutError):
        asyncio.run(i2v.poll_with_backoff(session, "T1"))


# ─── Resumable batch (process_one) ────────────────────────────────────────────

def _patch_io(monkeypatch, tmp_path):
    monkeypatch.setattr(i2v, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(i2v, "OUTPUT_DIR", tmp_path / "out")


def test_process_one_submits_and_downloads(tmp_path, monkeypatch):
    _patch_io(monkeypatch, tmp_path)

    async def fake_submit(session, rec, cfg):
        return "TASKABCDEF"

    async def fake_poll(session, task_id):
        return {"status": "succeed", "video_url": "http://v/clip.mp4"}

    monkeypatch.setattr(i2v, "submit_job", fake_submit)
    monkeypatch.setattr(i2v, "poll_with_backoff", fake_poll)

    sem = asyncio.Semaphore(1)
    session = FakeSession([], download_body=b"MP4DATA")
    rec = {"filename": "a.png", "checksum_sha256": "deadbeef"}
    state = {}

    result = asyncio.run(i2v.process_one(session, sem, rec, {}, state))
    assert result["status"] == "succeed"
    out = tmp_path / "out" / "a__TASKABCD.mp4"
    assert out.read_bytes() == b"MP4DATA"
    assert state["a.png"]["status"] == "succeed"


def test_process_one_resumes_without_resubmitting(tmp_path, monkeypatch):
    _patch_io(monkeypatch, tmp_path)

    submit_calls = {"n": 0}

    async def fake_submit(session, rec, cfg):
        submit_calls["n"] += 1
        return "SHOULD_NOT_HAPPEN"

    async def fake_poll(session, task_id):
        assert task_id == "EXISTING1"  # reused from state
        return {"status": "succeed", "video_url": "http://v/clip.mp4"}

    monkeypatch.setattr(i2v, "submit_job", fake_submit)
    monkeypatch.setattr(i2v, "poll_with_backoff", fake_poll)

    sem = asyncio.Semaphore(1)
    session = FakeSession([])
    rec = {"filename": "a.png", "checksum_sha256": "x"}
    state = {"a.png": {"task_id": "EXISTING1"}}

    result = asyncio.run(i2v.process_one(session, sem, rec, {}, state))
    assert result["task_id"] == "EXISTING1"
    assert submit_calls["n"] == 0  # never resubmitted


def test_process_one_isolates_failure(tmp_path, monkeypatch):
    _patch_io(monkeypatch, tmp_path)

    async def fake_submit(session, rec, cfg):
        raise RuntimeError("submit blew up")

    monkeypatch.setattr(i2v, "submit_job", fake_submit)

    sem = asyncio.Semaphore(1)
    session = FakeSession([])
    rec = {"filename": "a.png", "checksum_sha256": "x"}
    result = asyncio.run(i2v.process_one(session, sem, rec, {}, {}))
    assert result["status"] == "failed"
    assert "submit blew up" in result["error"]
