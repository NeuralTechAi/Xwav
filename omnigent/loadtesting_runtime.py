"""Bounded, dependency-free HTTP load profiles for the current job's local app."""

from __future__ import annotations

import asyncio
import json
import math
import os
import random
import time
from collections import deque
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

PROFILES = ("load", "stress", "spike", "soak")
NOTICE = (
    "Bounded HTTP service tests against this job's local app only. Web, Android and iOS "
    "user-agent samples share one traffic budget; these are not native-device "
    "or browser-rendering tests. "
    "Passing this run does not establish production capacity. Longer endurance runs "
    "can be configured "
    "in .xwav/loadtesting.json. Count-driven runs complete their request allocations; "
    "configured durations apply only to timed runs. Counts are exact; latency percentiles "
    "use up to 4096 samples."
)


MAX_REQUESTS = 100_000_000
LATENCY_SAMPLES = 4096


def validate_request_count(value: object) -> int:
    if type(value) is not int or not 1 <= value <= MAX_REQUESTS:
        raise ValueError("Total requests must be a whole number from 1 to 100,000,000")
    return value


def settings(root: Path, max_requests: int | None = None) -> dict:
    path = root / ".xwav/loadtesting.json"
    data = json.loads(path.read_text()) if path.is_file() else {}
    if not isinstance(data, dict):
        raise ValueError("Load testing configuration must be an object")
    if max_requests is not None:
        data["max_requests"] = validate_request_count(max_requests)
        data["request_mode"] = "count"
    defaults = {
        "concurrency": 4,
        "max_concurrency": 16,
        "requests_per_second": 20,
        "max_requests": 2000,
        "max_p95_ms": 1000,
        "max_error_percent": 1,
    }
    for key, default in defaults.items():
        data.setdefault(key, default)
    for key, low, high in (
        ("concurrency", 1, 16),
        ("max_concurrency", 1, 16),
        ("requests_per_second", 1, 50),
        ("max_requests", 1, MAX_REQUESTS),
        ("max_p95_ms", 1, 60000),
        ("max_error_percent", 0, 100),
    ):
        value = data[key]
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{key} must be an integer between {low} and {high}")
    if data["concurrency"] > data["max_concurrency"]:
        raise ValueError("concurrency must not exceed max_concurrency")
    data.setdefault("request_mode", "duration")
    if data["request_mode"] not in {"count", "duration"}:
        raise ValueError("request_mode must be count or duration")
    durations = data.setdefault("durations", {})
    if not isinstance(durations, dict):
        raise ValueError("durations must be an object")
    for profile, default in zip(PROFILES, (8, 12, 10, 30), strict=True):
        value = durations.setdefault(profile, default)
        if type(value) is not int or not 1 <= value <= (1800 if profile == "soak" else 120):
            raise ValueError(
                f"Invalid {profile} duration; soak allows 1–1800 seconds, others 1–120"
            )
    paths = data.setdefault("paths", ["/"])
    if (
        not isinstance(paths, list)
        or not 1 <= len(paths) <= 10
        or any(
            not isinstance(p, str)
            or not p.startswith("/")
            or p.startswith("//")
            or len(p) > 1024
            or any(ord(c) < 33 or ord(c) > 126 for c in p)
            or "#" in p
            or "\\" in p
            for p in paths
        )
    ):
        raise ValueError(
            "paths must contain 1–10 local, ASCII HTTP paths, without spaces or fragments"
        )
    return data


def discover(root: Path, max_requests: int | None = None) -> list[dict]:
    config = settings(root, max_requests)
    quotient, remainder = divmod(config["max_requests"], len(PROFILES))
    return [
        {
            "id": profile,
            "name": f"{profile.title()} test",
            "category": profile,
            "platform": "shared",
            "status": "pending",
            "config": config,
            "target_requests": quotient + (index < remainder)
            if config["request_mode"] == "count"
            else None,
        }
        for index, profile in enumerate(PROFILES)
    ]


def percentile(values: list[float], percent: float) -> float:
    return round(sorted(values)[max(0, math.ceil(len(values) * percent) - 1)], 2) if values else 0


class SampleTotals:
    """Exact counters and a fixed-size reservoir for sampled latency percentiles."""

    def __init__(self) -> None:
        self.requests = 0
        self.errors = 0
        self.bytes_sampled = 0
        self.maximum = 0.0
        self.latencies: list[float] = []
        self.status_codes: dict[str, int] = {}
        self.sample_errors: list[str] = []
        self.random = random.Random(0)

    def record(self, status: int, latency: float, size: int, error: str) -> None:
        self.requests += 1
        self.bytes_sampled += size
        self.maximum = max(self.maximum, latency)
        code = str(status)
        self.status_codes[code] = self.status_codes.get(code, 0) + 1
        if not 200 <= status < 400:
            self.errors += 1
            message = error or f"HTTP {status}"
            if len(self.sample_errors) < 5 and message not in self.sample_errors:
                self.sample_errors.append(message)
        if len(self.latencies) < LATENCY_SAMPLES:
            self.latencies.append(latency)
        else:
            index = self.random.randrange(self.requests)
            if index < LATENCY_SAMPLES:
                self.latencies[index] = latency

    def metrics(self) -> dict:
        return {
            "requests": self.requests,
            "errors": self.errors,
            "error_percent": round(self.errors * 100 / self.requests, 2) if self.requests else 0,
            "p50_ms": percentile(self.latencies, 0.5),
            "p95_ms": percentile(self.latencies, 0.95),
            "p99_ms": percentile(self.latencies, 0.99),
            "max_ms": round(self.maximum, 2),
            "bytes_sampled": self.bytes_sampled,
            "status_codes": dict(self.status_codes),
            "sample_errors": list(self.sample_errors),
            "latency_sample_size": len(self.latencies),
            "latency_percentiles_estimated": self.requests > LATENCY_SAMPLES,
        }


async def request(port: int, path: str, platform: str) -> tuple[int, float, int, str]:
    begin = time.monotonic()
    writer = None
    try:
        async with asyncio.timeout(2):
            reader, writer = await asyncio.open_connection("127.0.0.1", port, limit=32768)
            agent = {
                "web": "Xwav-LoadTest/Web",
                "android": "Mozilla/5.0 (Linux; Android 14) Xwav-LoadTest",
                "ios": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Xwav-LoadTest",
            }[platform]
            writer.write(
                (
                    f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n"
                    f"User-Agent: {agent}\r\nConnection: close\r\n\r\n"
                ).encode("ascii")
            )
            await writer.drain()
            head = await reader.readuntil(b"\r\n\r\n")
            status = int(head.split(b" ", 2)[1])
            if not 100 <= status <= 599:
                raise ValueError("Invalid HTTP status")
            # Capped payload sampling keeps large assets from dominating memory/bandwidth.
            body = await reader.read(16384)
            return status, (time.monotonic() - begin) * 1000, len(head) + len(body), ""
    except (
        OSError,
        ValueError,
        TimeoutError,
        asyncio.IncompleteReadError,
        asyncio.LimitOverrunError,
    ) as exc:
        return 0, (time.monotonic() - begin) * 1000, 0, type(exc).__name__
    finally:
        if writer:
            writer.close()
            with suppress(OSError):
                await writer.wait_closed()


def concurrency(profile: str, progress: float, config: dict) -> int:
    base, maximum = config["concurrency"], config["max_concurrency"]
    if profile == "stress":
        return max(1, math.ceil(maximum * min(1, progress + 0.1)))
    if profile == "spike":
        return maximum if 0.2 <= progress < 0.65 else 1
    return base


def traffic_rate(profile: str, progress: float, config: dict) -> float:
    maximum = config["requests_per_second"]
    if profile == "stress":
        return max(1, maximum * min(1, progress + 0.1))
    if profile == "spike":
        return maximum if 0.2 <= progress < 0.65 else max(1, maximum / 10)
    return maximum


async def measure(
    port: int,
    profile: str,
    config: dict,
    cancel: Path,
    publish: Callable[[dict], None],
    budget: dict,
    target_requests: int | None = None,
) -> dict:
    started = time.monotonic()
    duration = config["durations"][profile]
    totals = SampleTotals()
    platform_totals = {platform: SampleTotals() for platform in ("web", "android", "ios")}
    series: deque[dict] = deque(maxlen=1800)
    sent = 0
    pending: set[asyncio.Task] = set()
    next_request = started
    next_publish = started
    peak = 0

    def snapshot() -> dict:
        elapsed = max(0.001, time.monotonic() - started)
        metrics = totals.metrics()
        return {
            **metrics,
            "rps": round(totals.requests / elapsed, 2),
            "duration": round(elapsed, 2),
            "peak_concurrency": peak,
            "series": list(series),
            "platforms": {
                platform: stats.metrics() for platform, stats in platform_totals.items()
            },
        }

    async def sample(index: int) -> None:
        platform = ("web", "android", "ios")[index % 3]
        result = await request(port, config["paths"][index % len(config["paths"])], platform)
        totals.record(*result)
        platform_totals[platform].record(*result)

    while not cancel.exists():
        if target_requests is None:
            if time.monotonic() - started >= duration:
                break
        elif sent >= target_requests and not pending:
            break
        now = time.monotonic()
        progress = (
            (sent / max(1, target_requests))
            if target_requests is not None
            else (now - started) / duration
        )
        target = concurrency(profile, progress, config)
        if (
            now >= next_request
            and len(pending) < target
            and budget["remaining"] > 0
            and (target_requests is None or sent < target_requests)
        ):
            index = budget["sent"]
            budget["sent"] += 1
            sent += 1
            budget["remaining"] -= 1
            task = asyncio.create_task(sample(index))
            pending.add(task)
            task.add_done_callback(pending.discard)
            peak = max(peak, len(pending))
            next_request = now + 1 / traffic_rate(profile, progress, config)
        if now >= next_publish:
            summary = snapshot()
            series.append(
                {
                    "second": round(now - started, 1),
                    "requests": summary["requests"],
                    "p95_ms": summary["p95_ms"],
                    "errors": summary["errors"],
                    "concurrency": target,
                }
            )
            publish(summary)
            next_publish = now + (1 if now - started < 60 else 5)
        if budget["remaining"] <= 0 and not pending:
            break
        await asyncio.sleep(0.01)
    if pending:
        await asyncio.gather(*list(pending))
    metrics = snapshot()
    series.append(
        {
            "second": metrics["duration"],
            "requests": metrics["requests"],
            "p95_ms": metrics["p95_ms"],
            "errors": metrics["errors"],
            "concurrency": concurrency(profile, 1, config),
        }
    )
    metrics["series"] = list(series)
    complete = (
        totals.requests == target_requests
        if target_requests is not None
        else time.monotonic() - started >= duration
    )
    state = (
        "cancelled"
        if cancel.exists()
        else "blocked"
        if not complete
        else "failed"
        if (
            not metrics["requests"]
            or metrics["error_percent"] > config["max_error_percent"]
            or metrics["p95_ms"] > config["max_p95_ms"]
        )
        else "passed"
    )
    return {
        "status": state,
        "metrics": metrics,
        "reason": "Request budget exhausted before the configured duration"
        if state == "blocked"
        else "",
        "assessment": "Thresholds met within this bounded profile; capacity limit not established."
        if state == "passed"
        else "Review latency, error rates and traffic limits.",
    }


def worker(directory: Path, run_id: str, save: Callable, fingerprint: Callable) -> None:
    import runpy

    path = directory / f"{run_id}.json"
    report = json.loads(path.read_text())
    report["worker_pid"] = os.getpid()
    report["heartbeat_at"] = time.time()
    save(path, report)
    root = Path(report["workspace"])
    cancel = directory / f"{run_id}.cancel"
    try:
        preview = runpy.run_path(str(directory / "preview.py"))["preview"]
        status = preview()
        for _ in range(20):
            if status.get("state") != "starting" or cancel.exists():
                break
            time.sleep(0.5)
            status = preview()
        if status.get("state") != "ready":
            raise ValueError(str(status.get("message", "No runnable HTTP app")))
        port = status["port"]
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Invalid local app port")
        report["target"] = f"http://127.0.0.1:{port}/"
        config = report["checks"][0]["config"]
        budget = {"remaining": config["max_requests"], "sent": 0}
        for check in report["checks"]:
            if cancel.exists():
                check["status"] = "cancelled"
                continue
            if check.get("target_requests") == 0:
                check.update(
                    status="not_applicable",
                    reason="No requests allocated to this profile for this small total.",
                )
                continue
            if not budget["remaining"]:
                check.update(status="blocked", reason="Shared request budget exhausted")
                continue
            check["status"] = "running"
            save(path, report)

            def publish(metrics: dict, current=check) -> None:
                current["metrics"] = metrics
                report["heartbeat_at"] = time.time()
                save(path, report)

            check.update(
                asyncio.run(
                    measure(
                        port,
                        check["id"],
                        config,
                        cancel,
                        publish,
                        budget,
                        check.get("target_requests"),
                    )
                )
            )
            save(path, report)
        report.update(
            state="cancelled" if cancel.exists() else "complete",
            finished_at=time.time(),
            source_changed=fingerprint(root) != report["source_version"],
        )
    except (
        OSError,
        ValueError,
        RuntimeError,
        TypeError,
        KeyError,
        AttributeError,
        ImportError,
    ) as exc:
        report.update(state="error", error=str(exc), finished_at=time.time())
        for check in report["checks"]:
            if check["status"] in {"pending", "running"}:
                check.update(status="blocked", reason=str(exc))
    save(path, report)
