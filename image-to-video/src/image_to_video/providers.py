#!/usr/bin/env python3
"""
Pluggable image-to-video providers.

The pipeline (image_to_video_pipeline.py) owns the generic machinery — HTTP
retry, exponential-backoff polling, concurrency, resumability. Everything
provider-specific (endpoints, request payloads, response parsing, pricing)
lives behind the VideoProvider interface here, so a new backend is a small,
declarative class rather than a fork of the pipeline.

Add a provider by subclassing VideoProvider and registering it in PROVIDERS.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass


@dataclass
class CostEstimate:
    provider: str
    num_clips: int
    seconds_each: float
    per_clip: float
    currency: str
    total: float
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class StatusResult:
    """Normalized poll result. state ∈ {'succeed', 'failed', 'pending'}."""

    state: str
    video_url: str | None = None
    message: str | None = None


class VideoProvider(ABC):
    """
    Declarative adapter for one image-to-video backend.

    Implementations are stateless and side-effect free: they build requests and
    parse responses, but never perform I/O themselves (the pipeline does).
    """

    name: str

    # ── Submission ──
    @abstractmethod
    def build_submit_request(self, record: dict, job_config: dict) -> tuple[str, dict]:
        """Return (url, json_payload) for submitting one image2video job."""

    @abstractmethod
    def parse_submit_response(self, status: int, body: dict) -> str:
        """Return the task_id from a submit response, or raise on error."""

    # ── Polling ──
    @abstractmethod
    def status_url(self, task_id: str) -> str:
        """Return the URL to poll for a task's status."""

    @abstractmethod
    def parse_status(self, body: dict) -> StatusResult:
        """Normalize a status-poll response body into a StatusResult."""

    # ── Cost ──
    @abstractmethod
    def estimate_cost(self, job_config: dict, num_clips: int) -> CostEstimate:
        """Estimate the cost of generating num_clips with this job_config."""


class KlingProvider(VideoProvider):
    """Kling V3 image2video (api.kling.ai)."""

    name = "kling"
    SUBMIT_URL = "https://api.kling.ai/v1/videos/image2video"
    STATUS_URL = "https://api.kling.ai/v1/videos/image2video/{task_id}"
    MODEL_NAME = "kling-v3"

    DEFAULT_PROMPT = (
        "subtle expression shift, camera slowly pushes in, face fully in frame"
    )
    DEFAULT_NEGATIVE = (
        "blur, distortion, face morph, identity drift, anatomical distortion"
    )

    # Approximate USD/second by mode. Verify against current Kling pricing.
    PRICE_PER_SECOND = {"std": 0.028, "pro": 0.049}

    def build_submit_request(self, record: dict, job_config: dict) -> tuple[str, dict]:
        payload = {
            "model_name": self.MODEL_NAME,
            "image": record["base64"],  # raw base64, no data-URI prefix
            "prompt": job_config.get("prompt", self.DEFAULT_PROMPT),
            "negative_prompt": job_config.get("negative_prompt", self.DEFAULT_NEGATIVE),
            "cfg_scale": job_config.get("cfg_scale", 0.5),
            "mode": job_config.get("mode", "pro"),
            "duration": job_config.get("duration", 10),
            "aspect_ratio": job_config.get("aspect_ratio", "9:16"),
        }
        return self.SUBMIT_URL, payload

    def parse_submit_response(self, status: int, body: dict) -> str:
        if status >= 400:
            raise RuntimeError(f"Submit error {status}: {body}")
        return body["data"]["task_id"]

    def status_url(self, task_id: str) -> str:
        return self.STATUS_URL.format(task_id=task_id)

    def parse_status(self, body: dict) -> StatusResult:
        status = body.get("data", {}).get("task_status")
        if status == "succeed":
            videos = body["data"]["task_result"]["videos"]
            return StatusResult(state="succeed", video_url=videos[0]["url"])
        if status == "failed":
            msg = body["data"].get("task_status_msg", "unspecified failure")
            return StatusResult(state="failed", message=msg)
        return StatusResult(state="pending")

    def estimate_cost(self, job_config: dict, num_clips: int) -> CostEstimate:
        seconds = float(job_config.get("duration", 10))
        mode = job_config.get("mode", "pro")
        rate = self.PRICE_PER_SECOND.get(mode, self.PRICE_PER_SECOND["pro"])
        per_clip = round(seconds * rate, 4)
        return CostEstimate(
            provider=self.name,
            num_clips=num_clips,
            seconds_each=seconds,
            per_clip=per_clip,
            currency="USD",
            total=round(per_clip * num_clips, 2),
            note=f"approx; mode={mode} @ ${rate}/s",
        )


class GoEnhanceProvider(VideoProvider):
    """
    GoEnhance image-to-video (api.goenhance.ai).

    NOTE: endpoint paths and the response schema below follow GoEnhance's
    documented REST shape but should be verified against the current API
    before production use — they are isolated here so only this class changes.
    """

    name = "goenhance"
    BASE = "https://api.goenhance.ai/api/v1"
    SUBMIT_URL = f"{BASE}/video/image2video"
    STATUS_URL = f"{BASE}/video/status/{{task_id}}"

    DEFAULT_PROMPT = KlingProvider.DEFAULT_PROMPT
    DEFAULT_NEGATIVE = KlingProvider.DEFAULT_NEGATIVE

    PRICE_PER_SECOND = 0.04  # approximate USD/second; verify against pricing

    def build_submit_request(self, record: dict, job_config: dict) -> tuple[str, dict]:
        payload = {
            "image_base64": record["base64"],
            "prompt": job_config.get("prompt", self.DEFAULT_PROMPT),
            "negative_prompt": job_config.get("negative_prompt", self.DEFAULT_NEGATIVE),
            "duration": job_config.get("duration", 10),
            "aspect_ratio": job_config.get("aspect_ratio", "9:16"),
            "motion_strength": job_config.get("motion_strength", 0.5),
        }
        return self.SUBMIT_URL, payload

    def parse_submit_response(self, status: int, body: dict) -> str:
        if status >= 400:
            raise RuntimeError(f"Submit error {status}: {body}")
        # GoEnhance nests the id under data.task_id (fallback to top-level).
        data = body.get("data", body)
        task_id = data.get("task_id") or data.get("id")
        if not task_id:
            raise RuntimeError(f"No task_id in submit response: {body}")
        return task_id

    def status_url(self, task_id: str) -> str:
        return self.STATUS_URL.format(task_id=task_id)

    def parse_status(self, body: dict) -> StatusResult:
        data = body.get("data", body)
        status = (data.get("status") or "").lower()
        if status in ("succeed", "success", "completed", "done"):
            url = data.get("video_url") or (data.get("result", {}) or {}).get(
                "video_url"
            )
            return StatusResult(state="succeed", video_url=url)
        if status in ("failed", "error"):
            return StatusResult(
                state="failed", message=data.get("message", "unspecified failure")
            )
        return StatusResult(state="pending")

    def estimate_cost(self, job_config: dict, num_clips: int) -> CostEstimate:
        seconds = float(job_config.get("duration", 10))
        per_clip = round(seconds * self.PRICE_PER_SECOND, 4)
        return CostEstimate(
            provider=self.name,
            num_clips=num_clips,
            seconds_each=seconds,
            per_clip=per_clip,
            currency="USD",
            total=round(per_clip * num_clips, 2),
            note=f"approx; ${self.PRICE_PER_SECOND}/s",
        )


PROVIDERS: dict[str, type[VideoProvider]] = {
    KlingProvider.name: KlingProvider,
    GoEnhanceProvider.name: GoEnhanceProvider,
}


def get_provider(name: str) -> VideoProvider:
    """Instantiate a registered provider by name (case-insensitive)."""
    key = (name or "").lower()
    if key not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {', '.join(sorted(PROVIDERS))}"
        )
    return PROVIDERS[key]()
