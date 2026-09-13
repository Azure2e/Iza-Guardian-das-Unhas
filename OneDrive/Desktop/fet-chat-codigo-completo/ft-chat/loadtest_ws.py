#!/usr/bin/env python3
"""Teste de carga WebSocket do FT Chat.

  py -3 loadtest_ws.py --url http://127.0.0.1:3000 --clients 40 --messages 4
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import urllib.request

import websockets


def auth_token(base: str, name: str) -> str:
    req = urllib.request.Request(
        f"{base}/api/auth",
        data=json.dumps({"name": name}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("accessToken") or data.get("token") or ""


async def one_client(idx: int, ws_url: str, token: str, messages: int, results: dict):
    name = f"Load{idx:03d}"
    t0 = time.perf_counter()
    try:
        async with websockets.connect(ws_url, open_timeout=15, max_size=2**22) as ws:
            results["connect_ms"].append((time.perf_counter() - t0) * 1000)
            await asyncio.wait_for(ws.recv(), 8)
            await ws.send(json.dumps({"op": "join", "name": name, "token": token}))
            joined = False
            end = time.perf_counter() + 8
            while time.perf_counter() < end:
                data = json.loads(await asyncio.wait_for(ws.recv(), 5))
                if data.get("op") == "joined":
                    joined = True
                    break
                if data.get("op") in {"need_auth", "error", "banned"}:
                    results["errors"].append(f"{name} {data.get('op')} {data.get('text')}")
                    break
            if not joined:
                results["fail_join"] += 1
                return
            results["ok_join"] += 1
            for n in range(messages):
                s = time.perf_counter()
                await ws.send(json.dumps({
                    "op": "message",
                    "type": "text",
                    "text": f"lt {idx}-{n}",
                    "groupId": "aberto",
                    "clientId": f"lt-{idx}-{n}",
                }))
                results["sent"] += 1
                try:
                    await asyncio.wait_for(ws.recv(), 2)
                    results["rtt_ms"].append((time.perf_counter() - s) * 1000)
                except Exception:
                    results["lost"] += 1
    except Exception as exc:
        results["fail_conn"] += 1
        results["errors"].append(f"{name}: {type(exc).__name__}: {exc}")


async def run(base: str, clients: int, messages: int, concurrency: int):
    ws_url = base.replace("http://", "ws://").replace("https://", "wss://").rstrip("/") + "/ws"
    tokens = {i: auth_token(base, f"Load{i:03d}") for i in range(clients)}
    results = {
        "connect_ms": [], "rtt_ms": [], "ok_join": 0, "fail_join": 0,
        "fail_conn": 0, "sent": 0, "lost": 0, "errors": [],
    }
    sem = asyncio.Semaphore(concurrency)

    async def bound(i):
        async with sem:
            await one_client(i, ws_url, tokens[i], messages, results)

    t0 = time.perf_counter()
    await asyncio.gather(*(bound(i) for i in range(clients)))
    results["wall_s"] = time.perf_counter() - t0
    return results


def pct(xs, p):
    if not xs:
        return 0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, int(round((p / 100) * (len(xs) - 1)))))]


def summary(results, clients, messages):
    conn, rtt = results["connect_ms"], results["rtt_ms"]
    lines = [
        "=== Carga WebSocket FT Chat ===",
        f"Clientes={clients}  msgs/cliente={messages}  parede={results['wall_s']:.2f}s",
        f"Join OK={results['ok_join']}  join falhou={results['fail_join']}  conn falhou={results['fail_conn']}",
        f"Enviadas={results['sent']}  sem resposta em 2s={results['lost']}",
    ]
    if conn:
        lines.append(f"Handshake ms avg={statistics.mean(conn):.0f} p50={pct(conn,50):.0f} p95={pct(conn,95):.0f} max={max(conn):.0f}")
    if rtt:
        lines.append(f"Ida/volta ms avg={statistics.mean(rtt):.0f} p50={pct(rtt,50):.0f} p95={pct(rtt,95):.0f} max={max(rtt):.0f}")
        lines.append(f"Throughput ~ {results['sent'] / max(results['wall_s'], 0.001):.1f} envios/s")
    for err in results["errors"][:8]:
        lines.append(f"  ! {err}")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:3000")
    p.add_argument("--clients", type=int, default=20)
    p.add_argument("--messages", type=int, default=2)
    p.add_argument("--concurrency", type=int, default=10)
    args = p.parse_args()
    results = asyncio.run(run(args.url.rstrip("/"), args.clients, args.messages, args.concurrency))
    print(summary(results, args.clients, args.messages))


if __name__ == "__main__":
    main()
