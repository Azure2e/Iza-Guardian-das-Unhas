#!/usr/bin/env python3
"""Teste de carga HTTP do FT Chat.

  py -3 loadtest_http.py --url http://127.0.0.1:3000 --requests 80 --concurrency 20
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def hit(url: str, timeout: float = 8):
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read()
            ms = (time.perf_counter() - t0) * 1000
            return True, resp.status, ms, len(body)
    except Exception as exc:
        ms = (time.perf_counter() - t0) * 1000
        return False, str(exc), ms, 0


def auth(url: str, name: str):
    t0 = time.perf_counter()
    req = urllib.request.Request(
        f"{url}/api/auth",
        data=json.dumps({"name": name}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ms = (time.perf_counter() - t0) * 1000
            ok = bool(data.get("token") or data.get("accessToken"))
            return ok, resp.status, ms
    except Exception as exc:
        return False, str(exc), (time.perf_counter() - t0) * 1000


def pct(xs, p):
    if not xs:
        return 0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round((p / 100) * (len(xs) - 1))))]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:3000")
    p.add_argument("--requests", type=int, default=60)
    p.add_argument("--concurrency", type=int, default=15)
    args = p.parse_args()
    base = args.url.rstrip("/")

    health_ms, fail = [], 0
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futs = [pool.submit(hit, f"{base}/api/health") for _ in range(args.requests)]
        for fut in as_completed(futs):
            ok, status, ms, _ = fut.result()
            health_ms.append(ms)
            if not ok or status != 200:
                fail += 1
    wall = time.perf_counter() - t0

    static_ms = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futs = [pool.submit(hit, f"{base}/") for _ in range(max(10, args.requests // 3))]
        for fut in as_completed(futs):
            ok, status, ms, _ = fut.result()
            if ok:
                static_ms.append(ms)

    auth_ms, auth_fail = [], 0
    with ThreadPoolExecutor(max_workers=min(8, args.concurrency)) as pool:
        futs = [pool.submit(auth, base, f"Http{i}") for i in range(12)]
        for i, fut in enumerate(as_completed(futs)):
            ok, status, ms = fut.result()
            auth_ms.append(ms)
            if not ok:
                auth_fail += 1

    print("=== Carga HTTP FT Chat ===")
    print(f"Health {args.requests} req em {wall:.2f}s  falhas={fail}  ~{args.requests/max(wall,0.001):.1f} req/s")
    if health_ms:
        print(f"Health ms avg={statistics.mean(health_ms):.0f} p50={pct(health_ms,50):.0f} p95={pct(health_ms,95):.0f} max={max(health_ms):.0f}")
    if static_ms:
        print(f"GET /  ms avg={statistics.mean(static_ms):.0f} p50={pct(static_ms,50):.0f} p95={pct(static_ms,95):.0f}")
    if auth_ms:
        print(f"POST /api/auth avg={statistics.mean(auth_ms):.0f} ms  falhas={auth_fail}/12")


if __name__ == "__main__":
    main()
