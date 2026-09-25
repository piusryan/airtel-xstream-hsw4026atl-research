from __future__ import annotations

import argparse
import ipaddress
import json
import secrets
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ElementTree
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast
from urllib.parse import urlsplit

DEFAULT_TARGET = "192.168.1.10"
DEFAULT_PORTS = (22, 23, 53, 80, 443, 5555, 8008, 8009, 8080, 8443)
PORT_LABELS = {
    22: "SSH",
    23: "Telnet",
    53: "DNS/TCP",
    80: "HTTP",
    443: "HTTPS",
    5555: "ADB",
    8008: "DIAL",
    8009: "Service",
    8080: "HTTP alt",
    8443: "HTTPS alt",
}
ALLOWED_NETWORKS = (
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("169.254.0.0/16"),
)


class ValidationError(ValueError):
    pass


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_target(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Enter a target IPv4 address.")
    candidate = value.strip()
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError as exc:
        raise ValidationError("The target must be a literal IPv4 address.") from exc
    if not isinstance(address, ipaddress.IPv4Address):
        raise ValidationError("Only IPv4 targets are supported by this dashboard.")
    if not any(address in network for network in ALLOWED_NETWORKS):
        raise ValidationError("The target must be on a private, loopback, or link-local IPv4 network.")
    return str(address)


def normalize_timeout(value: Any) -> float:
    if isinstance(value, bool):
        raise ValidationError("Enter a valid timeout.")
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Enter a valid timeout.") from exc
    if not 0.2 <= timeout <= 5.0:
        raise ValidationError("Timeout must be between 0.2 and 5 seconds.")
    return round(timeout, 2)


def normalize_ports(value: Any) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise ValidationError("Select at least one approved port.")
    normalized: list[int] = []
    for item in value:
        if isinstance(item, bool):
            raise ValidationError("Invalid port selection.")
        try:
            port = int(item)
        except (TypeError, ValueError) as exc:
            raise ValidationError("Invalid port selection.") from exc
        if port not in DEFAULT_PORTS:
            raise ValidationError("Only the dashboard's fixed read-only port set is allowed.")
        normalized.append(port)
    return tuple(sorted(set(normalized)))


def check_port(target: str, port: int, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with socket.create_connection((target, port), timeout=timeout):
            state = "open"
            detail = "TCP connection completed"
    except socket.timeout:
        state = "timeout"
        detail = "Connection timed out"
    except ConnectionRefusedError:
        state = "closed"
        detail = "Connection refused"
    except OSError as exc:
        state = "error"
        detail = exc.strerror or str(exc)
    elapsed = round((time.perf_counter() - started) * 1000, 1)
    return {
        "port": port,
        "label": PORT_LABELS.get(port, "TCP"),
        "state": state,
        "latency_ms": elapsed,
        "detail": detail,
    }


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_dial_description(payload: bytes) -> dict[str, str]:
    root = ElementTree.fromstring(payload)
    values: dict[str, str] = {}
    wanted = {"friendlyName", "manufacturer", "modelName", "modelNumber"}
    for element in root.iter():
        name = local_name(element.tag)
        if name in wanted and name not in values and element.text:
            values[name] = element.text.strip()
    if "modelName" not in values and "friendlyName" not in values:
        raise ValueError("DIAL response did not contain a model identity.")
    return values


def http_get(
    url: str,
    timeout: float,
    context: ssl.SSLContext | None = None,
    max_bytes: int = 8192,
) -> tuple[int, bytes, str | None]:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/xml,text/xml,text/plain;q=0.8,*/*;q=0.1",
            "Connection": "close",
            "User-Agent": "XStream-ReadOnly-Diagnostic/1.0",
        },
    )
    opener = urllib.request.build_opener(NoRedirectHandler())
    if context is not None:
        opener.add_handler(urllib.request.HTTPSHandler(context=context))
    with opener.open(request, timeout=timeout) as response:
        payload = response.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise ValueError("Response exceeded the fixed diagnostic size limit.")
        server = response.headers.get("Server")
        return response.status, payload, server


def probe_dial(target: str, timeout: float) -> dict[str, Any]:
    url = f"http://{target}:8008/ssdp/device-desc.xml"
    try:
        status, payload, server = http_get(url, timeout)
        identity = parse_dial_description(payload)
        return {
            "state": "ok",
            "url": url,
            "status": status,
            "server": server,
            **identity,
        }
    except urllib.error.HTTPError as exc:
        return {"state": "http_error", "url": url, "status": exc.code, "detail": str(exc.reason)}
    except (urllib.error.URLError, TimeoutError, ValueError, ElementTree.ParseError) as exc:
        reason = getattr(exc, "reason", exc)
        return {"state": "error", "url": url, "detail": str(reason)}


def probe_https(target: str, timeout: float) -> dict[str, Any]:
    url = f"https://{target}:8443/"
    context = ssl.create_default_context()
    try:
        status, _, server = http_get(url, timeout, context=context, max_bytes=1024)
        return {"state": "ok", "url": url, "status": status, "server": server}
    except urllib.error.HTTPError as exc:
        return {"state": "http_error", "url": url, "status": exc.code, "detail": str(exc.reason)}
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        return {"state": "error", "url": url, "detail": str(reason)}


def run_scan(
    target: str,
    ports: tuple[int, ...],
    timeout: float,
    include_service_probes: bool = True,
) -> dict[str, Any]:
    started_at = utc_timestamp()
    started = time.perf_counter()
    port_results = [check_port(target, port, timeout) for port in ports]
    open_ports = {item["port"] for item in port_results if item["state"] == "open"}
    dial_probe: dict[str, Any]
    https_probe: dict[str, Any]
    if not include_service_probes or 8008 not in ports:
        dial_probe = {"state": "skipped", "detail": "Port 8008 was not selected or was not open."}
    elif 8008 in open_ports:
        dial_probe = probe_dial(target, timeout)
    else:
        dial_probe = {"state": "skipped", "detail": "TCP 8008 was not open."}
    if not include_service_probes or 8443 not in ports:
        https_probe = {"state": "skipped", "detail": "Port 8443 was not selected or was not open."}
    elif 8443 in open_ports:
        https_probe = probe_https(target, timeout)
    else:
        https_probe = {"state": "skipped", "detail": "TCP 8443 was not open."}
    return {
        "schema_version": 1,
        "target": target,
        "started_at": started_at,
        "finished_at": utc_timestamp(),
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        "timeout_seconds": timeout,
        "read_only": True,
        "scope": [
            "TCP connection attempts against the selected fixed ports",
            "GET /ssdp/device-desc.xml on TCP 8008 when open",
            "GET / on TCP 8443 when open",
        ],
        "excluded": [
            "No reset, erase, flash, unlock, reboot, login, ADB enablement, or package action",
            "No arbitrary hostnames, public addresses, URLs, or ports",
            "No response body stored beyond bounded identity fields",
        ],
        "ports": port_results,
        "summary": {
            "selected": len(port_results),
            "open": len(open_ports),
            "closed": sum(item["state"] == "closed" for item in port_results),
            "timeout": sum(item["state"] == "timeout" for item in port_results),
            "error": sum(item["state"] == "error" for item in port_results),
        },
        "dial": dial_probe,
        "https_8443": https_probe,
    }


def markdown_export(data: dict[str, Any]) -> str:
    def cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "# XStream Read-only Diagnostic",
        "",
        f"- Target: `{data.get('target', 'unknown')}`",
        f"- Started: `{data.get('started_at', 'unknown')}`",
        f"- Finished: `{data.get('finished_at', 'unknown')}`",
        f"- Read-only: `{str(data.get('read_only', False)).lower()}`",
        "",
        "## TCP results",
        "",
        "| Port | Label | State | Latency | Detail |",
        "|---:|---|---|---:|---|",
    ]
    for item in data.get("ports", []):
        lines.append(
            f"| {cell(item.get('port'))} | {cell(item.get('label'))} | "
            f"{cell(item.get('state'))} | {cell(item.get('latency_ms'))} ms | {cell(item.get('detail'))} |"
        )
    dial = data.get("dial", {})
    https = data.get("https_8443", {})
    lines.extend(
        [
            "",
            "## Service probes",
            "",
            f"- DIAL: `{cell(dial.get('state'))}`; manufacturer `{cell(dial.get('manufacturer', '—'))}`; "
            f"model `{cell(dial.get('modelName', dial.get('friendlyName', '—')))}`",
            f"- HTTPS 8443: `{cell(https.get('state'))}`; status `{cell(https.get('status', '—'))}`",
            "",
            "## Safety scope",
            "",
        ]
    )
    lines.extend(f"- {cell(item)}" for item in data.get("excluded", []))
    return "\n".join(lines) + "\n"


def port_controls() -> str:
    controls = []
    for port in DEFAULT_PORTS:
        controls.append(
            '<label class="port-chip">'
            f'<input type="checkbox" name="ports" value="{port}" checked>'
            f"<span><strong>{port}</strong><small>{PORT_LABELS[port]}</small></span>"
            "</label>"
        )
    return "".join(controls)


PAGE_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="csrf-token" content="__TOKEN__">
<title>XStream Read-only Diagnostic</title>
<style nonce="__NONCE__">
:root {
  color-scheme: dark;
  --bg: #07110f;
  --panel: rgba(17, 35, 31, 0.88);
  --panel-strong: #132a25;
  --line: #29483f;
  --text: #edf8f3;
  --muted: #9bb8ad;
  --accent: #53e0a4;
  --accent-strong: #1fc784;
  --warning: #ffc76a;
  --danger: #ff7d7d;
  --blue: #7dc9ff;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--text);
  background:
    radial-gradient(circle at 12% 0%, rgba(31, 199, 132, 0.16), transparent 33rem),
    radial-gradient(circle at 100% 15%, rgba(80, 160, 255, 0.11), transparent 30rem),
    var(--bg);
}
body::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  opacity: 0.18;
  background-image: linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: linear-gradient(to bottom, black, transparent 80%);
}
.shell { width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 38px 0 56px; position: relative; }
header { display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; margin-bottom: 24px; }
.eyebrow { margin: 0 0 8px; color: var(--accent); font-size: 0.78rem; font-weight: 800; letter-spacing: 0.16em; text-transform: uppercase; }
h1 { margin: 0; max-width: 760px; font-size: clamp(2rem, 5vw, 4.3rem); line-height: 0.98; letter-spacing: -0.055em; }
.lede { max-width: 720px; color: var(--muted); font-size: 1rem; line-height: 1.65; margin: 16px 0 0; }
.badge { border: 1px solid rgba(83, 224, 164, 0.45); background: rgba(83, 224, 164, 0.09); color: var(--accent); border-radius: 999px; padding: 9px 13px; font-size: 0.78rem; font-weight: 800; white-space: nowrap; }
.grid { display: grid; grid-template-columns: minmax(290px, 0.78fr) minmax(0, 1.4fr); gap: 18px; align-items: start; }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 22px; box-shadow: 0 24px 70px rgba(0,0,0,0.26); backdrop-filter: blur(16px); overflow: hidden; }
.panel-head { display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 20px 22px; border-bottom: 1px solid var(--line); }
.panel-head h2 { margin: 0; font-size: 1rem; letter-spacing: -0.01em; }
.panel-body { padding: 22px; }
.field { display: grid; gap: 8px; margin-bottom: 20px; }
.field label, legend { color: var(--muted); font-size: 0.82rem; font-weight: 700; }
input[type="text"], input[type="number"] { width: 100%; border: 1px solid var(--line); border-radius: 12px; color: var(--text); background: #081713; padding: 12px 13px; font: inherit; outline: none; }
input[type="text"]:focus, input[type="number"]:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(83, 224, 164, 0.12); }
fieldset { border: 0; padding: 0; margin: 0 0 20px; }
legend { margin-bottom: 10px; }
.port-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.port-chip { position: relative; cursor: pointer; }
.port-chip input { position: absolute; opacity: 0; pointer-events: none; }
.port-chip span { min-height: 54px; border: 1px solid var(--line); border-radius: 12px; padding: 9px 11px; display: flex; align-items: center; justify-content: space-between; gap: 8px; background: rgba(5, 18, 15, 0.45); transition: 140ms ease; }
.port-chip strong { font-size: 0.94rem; }
.port-chip small { color: var(--muted); font-size: 0.68rem; text-align: right; }
.port-chip input:checked + span { border-color: rgba(83, 224, 164, 0.58); background: rgba(83, 224, 164, 0.08); color: var(--accent); }
.port-chip input:focus-visible + span { outline: 3px solid rgba(83, 224, 164, 0.22); outline-offset: 2px; }
.setting-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: end; }
.authorize { display: flex; gap: 10px; align-items: flex-start; border: 1px solid rgba(255, 199, 106, 0.35); background: rgba(255, 199, 106, 0.07); border-radius: 13px; padding: 12px; color: #ffe0a8; font-size: 0.82rem; line-height: 1.45; margin-bottom: 14px; }
.authorize input { accent-color: var(--warning); margin-top: 2px; }
button { border: 0; border-radius: 12px; font: inherit; font-weight: 800; cursor: pointer; transition: 140ms ease; }
button:disabled { cursor: not-allowed; opacity: 0.42; }
.primary { width: 100%; padding: 13px 16px; color: #04110c; background: linear-gradient(135deg, var(--accent), var(--accent-strong)); box-shadow: 0 10px 30px rgba(31, 199, 132, 0.18); }
.primary:hover:not(:disabled) { transform: translateY(-1px); filter: brightness(1.06); }
.safety-note { margin: 14px 0 0; color: var(--muted); font-size: 0.76rem; line-height: 1.5; }
.results-panel { min-height: 520px; }
.empty { min-height: 420px; display: grid; place-items: center; text-align: center; color: var(--muted); padding: 34px; }
.empty-mark { width: 72px; height: 72px; border-radius: 22px; display: grid; place-items: center; margin: 0 auto 18px; border: 1px solid var(--line); background: rgba(83, 224, 164, 0.07); color: var(--accent); font-size: 1.8rem; }
.empty h2 { color: var(--text); margin: 0 0 8px; }
.empty p { margin: 0 auto; max-width: 440px; line-height: 1.6; }
.result-content { display: none; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; padding: 18px 22px 0; }
.metric { border: 1px solid var(--line); background: rgba(5, 18, 15, 0.42); border-radius: 14px; padding: 13px; }
.metric strong { display: block; font-size: 1.45rem; letter-spacing: -0.04em; }
.metric span { color: var(--muted); font-size: 0.72rem; }
.table-wrap { overflow-x: auto; padding: 18px 22px; }
table { border-collapse: collapse; width: 100%; min-width: 650px; }
th, td { border-bottom: 1px solid var(--line); padding: 11px 9px; text-align: left; font-size: 0.82rem; }
th { color: var(--muted); font-size: 0.69rem; letter-spacing: 0.08em; text-transform: uppercase; }
tbody tr:last-child td { border-bottom: 0; }
.state { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 4px 8px; font-size: 0.7rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.05em; }
.state::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.state.open, .state.ok { color: var(--accent); background: rgba(83, 224, 164, 0.1); }
.state.closed, .state.skipped { color: var(--muted); background: rgba(155, 184, 173, 0.08); }
.state.timeout, .state.http_error, .state.error { color: var(--warning); background: rgba(255, 199, 106, 0.1); }
.services { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; padding: 0 22px 20px; }
.service { border: 1px solid var(--line); border-radius: 15px; background: rgba(5, 18, 15, 0.4); padding: 15px; }
.service h3 { margin: 0 0 10px; font-size: 0.85rem; }
.service dl { margin: 0; display: grid; grid-template-columns: minmax(76px, auto) 1fr; gap: 7px 12px; font-size: 0.77rem; }
.service dt { color: var(--muted); }
.service dd { margin: 0; overflow-wrap: anywhere; }
.actions { display: flex; justify-content: flex-end; gap: 9px; padding: 16px 22px; border-top: 1px solid var(--line); }
.secondary { color: var(--text); background: #1a332c; border: 1px solid var(--line); padding: 9px 12px; }
.secondary:hover:not(:disabled) { border-color: var(--accent); }
.status { min-height: 20px; margin: 12px 0 0; color: var(--muted); font-size: 0.76rem; line-height: 1.45; }
.status.error { color: var(--danger); }
.scope { margin-top: 18px; border-color: rgba(125, 201, 255, 0.28); background: rgba(22, 53, 66, 0.54); }
.scope h2 { color: var(--blue); }
.scope ul { margin: 0; padding-left: 20px; color: var(--muted); line-height: 1.65; font-size: 0.82rem; }
footer { color: var(--muted); text-align: center; font-size: 0.74rem; margin-top: 22px; }
@media (max-width: 860px) {
  .grid { grid-template-columns: 1fr; }
  .results-panel { min-height: auto; }
  .empty { min-height: 280px; }
}
@media (max-width: 560px) {
  .shell { width: min(100% - 20px, 1120px); padding-top: 24px; }
  header { flex-direction: column; }
  .summary-grid { grid-template-columns: 1fr 1fr; }
  .services { grid-template-columns: 1fr; }
  .port-grid { grid-template-columns: 1fr 1fr; }
  .actions { justify-content: stretch; }
  .actions button { flex: 1; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
</style>
</head>
<body>
<div class="shell">
<header>
  <div>
    <p class="eyebrow">Authorized local research</p>
    <h1>XStream read-only diagnostic</h1>
    <p class="lede">A local evidence tool for the HSW4026ATL investigation. It opens a small fixed set of TCP connections and makes two bounded GET requests only when the matching service is reachable.</p>
  </div>
  <span class="badge">No device writes</span>
</header>
<main class="grid">
  <section class="panel" aria-labelledby="scan-title">
    <div class="panel-head"><h2 id="scan-title">Scan controls</h2><span class="state skipped">Local only</span></div>
    <div class="panel-body">
      <form id="scan-form">
        <div class="field">
          <label for="target">Private target IPv4 address</label>
          <input id="target" name="target" type="text" value="__DEFAULT_TARGET__" inputmode="decimal" autocomplete="off" spellcheck="false" required>
        </div>
        <fieldset>
          <legend>Approved TCP checks</legend>
          <div class="port-grid">__PORT_CONTROLS__</div>
        </fieldset>
        <div class="setting-row">
          <div class="field">
            <label for="timeout">Timeout per check</label>
            <input id="timeout" name="timeout" type="number" min="0.2" max="5" step="0.1" value="1.5" required>
          </div>
        </div>
        <label class="authorize">
          <input id="authorization" type="checkbox" required>
          <span>I own this device or have explicit permission to perform these read-only checks.</span>
        </label>
        <button class="primary" id="run-button" type="submit">Run diagnostics</button>
        <p class="safety-note">The server rejects public IPs, hostnames, arbitrary ports, redirects, and missing authorization. It never logs in, reboots, unlocks, or writes to the target.</p>
        <p class="status" id="status" role="status" aria-live="polite"></p>
      </form>
    </div>
  </section>
  <section class="panel results-panel" aria-labelledby="results-title">
    <div class="panel-head"><h2 id="results-title">Observation log</h2><span id="run-time" class="state skipped">Not run</span></div>
    <div class="empty" id="empty-state">
      <div>
        <div class="empty-mark">⌁</div>
        <h2>Waiting for a read-only scan</h2>
        <p>Results appear here with explicit open, closed, timeout, and error states. Export creates a local file in your browser.</p>
      </div>
    </div>
    <div class="result-content" id="result-content">
      <div class="summary-grid">
        <div class="metric"><strong id="metric-open">0</strong><span>Open ports</span></div>
        <div class="metric"><strong id="metric-closed">0</strong><span>Closed ports</span></div>
        <div class="metric"><strong id="metric-timeout">0</strong><span>Timeouts</span></div>
        <div class="metric"><strong id="metric-duration">0 ms</strong><span>Total duration</span></div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Port</th><th>Service</th><th>State</th><th>Latency</th><th>Detail</th></tr></thead>
          <tbody id="port-results"></tbody>
        </table>
      </div>
      <div class="services">
        <article class="service"><h3>DIAL identity</h3><dl id="dial-details"></dl></article>
        <article class="service"><h3>HTTPS 8443</h3><dl id="https-details"></dl></article>
      </div>
      <div class="actions">
        <button class="secondary" id="download-json" type="button" disabled>Download JSON</button>
        <button class="secondary" id="download-markdown" type="button" disabled>Download Markdown</button>
      </div>
    </div>
  </section>
  <section class="panel scope">
    <div class="panel-head"><h2>Enforced boundary</h2><span class="state ok">Read-only</span></div>
    <div class="panel-body">
      <ul>
        <li>Targets are limited to RFC1918, loopback, and link-local IPv4 literals.</li>
        <li>Ports are limited to the ten services displayed in the interface.</li>
        <li>The only HTTP methods are bounded GET requests to fixed DIAL and HTTPS paths.</li>
        <li>Redirects are rejected; TLS certificate verification remains enabled.</li>
        <li>No evidence is written to the target, and exports are generated in your browser.</li>
      </ul>
    </div>
  </section>
</main>
<footer>Runs on 127.0.0.1 only · Source and logs remain under your control</footer>
</div>
<script nonce="__NONCE__">
const form = document.querySelector('#scan-form');
const runButton = document.querySelector('#run-button');
const statusBox = document.querySelector('#status');
const emptyState = document.querySelector('#empty-state');
const resultContent = document.querySelector('#result-content');
const portResults = document.querySelector('#port-results');
const dialDetails = document.querySelector('#dial-details');
const httpsDetails = document.querySelector('#https-details');
const downloadJson = document.querySelector('#download-json');
const downloadMarkdown = document.querySelector('#download-markdown');
const token = document.querySelector('meta[name="csrf-token"]').content;
let currentData = null;

function setText(selector, value) {
  document.querySelector(selector).textContent = value;
}

function stateBadge(value) {
  const badge = document.createElement('span');
  badge.className = `state ${value}`;
  badge.textContent = value.replaceAll('_', ' ');
  return badge;
}

function addDefinition(list, label, value) {
  const term = document.createElement('dt');
  const detail = document.createElement('dd');
  term.textContent = label;
  detail.textContent = value;
  list.append(term, detail);
}

function renderPorts(items) {
  portResults.replaceChildren();
  for (const item of items) {
    const row = document.createElement('tr');
    const port = document.createElement('td');
    const service = document.createElement('td');
    const stateCell = document.createElement('td');
    const latency = document.createElement('td');
    const detail = document.createElement('td');
    port.textContent = item.port;
    service.textContent = item.label;
    stateCell.append(stateBadge(item.state));
    latency.textContent = `${item.latency_ms} ms`;
    detail.textContent = item.detail;
    row.append(port, service, stateCell, latency, detail);
    portResults.append(row);
  }
}

function renderServices(data) {
  dialDetails.replaceChildren();
  httpsDetails.replaceChildren();
  addDefinition(dialDetails, 'State', data.dial.state);
  addDefinition(dialDetails, 'Manufacturer', data.dial.manufacturer || data.dial.friendlyName || '—');
  addDefinition(dialDetails, 'Model', data.dial.modelName || data.dial.modelNumber || '—');
  addDefinition(dialDetails, 'HTTP', data.dial.status ?? (data.dial.detail || '—'));
  addDefinition(httpsDetails, 'State', data.https_8443.state);
  addDefinition(httpsDetails, 'HTTP', data.https_8443.status ?? (data.https_8443.detail || '—'));
  addDefinition(httpsDetails, 'Server', data.https_8443.server || '—');
  addDefinition(httpsDetails, 'Path', '/');
}

function render(data) {
  currentData = data;
  emptyState.style.display = 'none';
  resultContent.style.display = 'block';
  setText('#metric-open', data.summary.open);
  setText('#metric-closed', data.summary.closed);
  setText('#metric-timeout', data.summary.timeout);
  setText('#metric-duration', `${data.duration_ms} ms`);
  setText('#run-time', new Date(data.finished_at).toLocaleString());
  renderPorts(data.ports);
  renderServices(data);
  downloadJson.disabled = false;
  downloadMarkdown.disabled = false;
}

function markdownFor(data) {
  const cell = (value) => String(value ?? '—').replaceAll('|', '\\|').replaceAll('\n', ' ');
  const lines = [
    '# XStream Read-only Diagnostic',
    '',
    `- Target: \`${cell(data.target)}\``,
    `- Started: \`${cell(data.started_at)}\``,
    `- Finished: \`${cell(data.finished_at)}\``,
    `- Read-only: \`${String(data.read_only).toLowerCase()}\``,
    '',
    '## TCP results',
    '',
    '| Port | Service | State | Latency | Detail |',
    '|---:|---|---|---:|---|',
  ];
  for (const item of data.ports) {
    lines.push(`| ${cell(item.port)} | ${cell(item.label)} | ${cell(item.state)} | ${cell(item.latency_ms)} ms | ${cell(item.detail)} |`);
  }
  lines.push('', '## Service probes', '');
  lines.push(`- DIAL: \`${cell(data.dial.state)}\`; manufacturer \`${cell(data.dial.manufacturer)}\`; model \`${cell(data.dial.modelName)}\``);
  lines.push(`- HTTPS 8443: \`${cell(data.https_8443.state)}\`; status \`${cell(data.https_8443.status)}\``);
  lines.push('', '## Safety scope', '');
  for (const item of data.excluded) lines.push(`- ${cell(item)}`);
  return `${lines.join('\n')}\n`;
}

function download(name, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  const selectedPorts = [...form.querySelectorAll('input[name="ports"]:checked')].map((input) => Number(input.value));
  runButton.disabled = true;
  runButton.textContent = 'Running…';
  statusBox.className = 'status';
  statusBox.textContent = 'Opening only the selected TCP connections…';
  try {
    const response = await fetch('/api/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
      body: JSON.stringify({
        target: document.querySelector('#target').value,
        timeout: Number(document.querySelector('#timeout').value),
        ports: selectedPorts,
        confirm_authorization: document.querySelector('#authorization').checked,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The diagnostic request failed.');
    render(data);
    statusBox.textContent = `Completed read-only observations for ${data.target}.`;
  } catch (error) {
    statusBox.className = 'status error';
    statusBox.textContent = error instanceof Error ? error.message : String(error);
  } finally {
    runButton.disabled = false;
    runButton.textContent = 'Run diagnostics';
  }
});

downloadJson.addEventListener('click', () => {
  if (!currentData) return;
  const stamp = currentData.finished_at.replaceAll(':', '').replaceAll('-', '');
  download(`xstream-diagnostic-${stamp}.json`, JSON.stringify(currentData, null, 2), 'application/json');
});

downloadMarkdown.addEventListener('click', () => {
  if (!currentData) return;
  const stamp = currentData.finished_at.replaceAll(':', '').replaceAll('-', '');
  download(`xstream-diagnostic-${stamp}.md`, markdownFor(currentData), 'text/markdown');
});
</script>
</body>
</html>
"""


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], token: str, nonce: str, default_target: str) -> None:
        super().__init__(address, DashboardHandler)
        self.token = token
        self.nonce = nonce
        self.default_target = default_target
        self.page = (
            PAGE_TEMPLATE.replace("__TOKEN__", token)
            .replace("__NONCE__", nonce)
            .replace("__DEFAULT_TARGET__", default_target)
            .replace("__PORT_CONTROLS__", port_controls())
        ).encode("utf-8")


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "XStreamDiagnostics/1.0"
    sys_version = ""

    @property
    def dashboard_server(self) -> DashboardServer:
        return cast(DashboardServer, self.server)

    def log_message(self, format: str, *args: Any) -> None:
        return None

    def allowed_hosts(self) -> set[str]:
        port = self.dashboard_server.server_port
        return {f"127.0.0.1:{port}", f"localhost:{port}"}

    def allowed_origins(self) -> set[str]:
        port = self.dashboard_server.server_port
        return {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    def host_allowed(self) -> bool:
        return self.headers.get("Host", "") in self.allowed_hosts()

    def send_bytes(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            f"default-src 'none'; style-src 'nonce-{self.dashboard_server.nonce}'; "
            f"script-src 'nonce-{self.dashboard_server.nonce}'; connect-src 'self'; "
            "img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_bytes(status, body, "application/json; charset=utf-8")

    def do_HEAD(self) -> None:
        if not self.host_allowed():
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "Host is not allowed."})
            return
        if urlsplit(self.path).path == "/":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(self.dashboard_server.page)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_GET(self) -> None:
        if not self.host_allowed():
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "Host is not allowed."})
            return
        path = urlsplit(self.path).path
        if path == "/":
            self.send_bytes(HTTPStatus.OK, self.dashboard_server.page, "text/html; charset=utf-8")
            return
        if path == "/api/health":
            self.send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "read_only": True,
                    "bind": "127.0.0.1",
                    "default_target": self.dashboard_server.default_target,
                },
            )
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_POST(self) -> None:
        if not self.host_allowed():
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "Host is not allowed."})
            return
        if urlsplit(self.path).path != "/api/scan":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        origin = self.headers.get("Origin")
        if origin and origin not in self.allowed_origins():
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "Origin is not allowed."})
            return
        supplied_token = self.headers.get("X-CSRF-Token", "")
        if not secrets.compare_digest(supplied_token, self.dashboard_server.token):
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "Request token is invalid."})
            return
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("application/json"):
            self.send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "Use application/json."})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            content_length = 0
        if content_length <= 0 or content_length > 4096:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid request size."})
            return
        try:
            payload = json.loads(self.rfile.read(content_length))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON."})
            return
        if not isinstance(payload, dict):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid request."})
            return
        if payload.get("confirm_authorization") is not True:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Authorization confirmation is required."})
            return
        try:
            target = validate_target(payload.get("target"))
            ports = normalize_ports(payload.get("ports"))
            timeout = normalize_timeout(payload.get("timeout"))
            result = run_scan(target, ports, timeout)
        except ValidationError as exc:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        except Exception:
            self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "The read-only scan failed safely."})
            return
        self.send_json(HTTPStatus.OK, result)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local read-only XStream network diagnostic dashboard")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--default-target", default=DEFAULT_TARGET)
    parser.add_argument("--open-browser", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1024 <= args.port <= 65535:
        raise SystemExit("Port must be between 1024 and 65535.")
    try:
        default_target = validate_target(args.default_target)
    except ValidationError as exc:
        raise SystemExit(str(exc)) from exc
    token = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(24)
    server = DashboardServer(("127.0.0.1", args.port), token, nonce, default_target)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"XStream read-only diagnostic dashboard: {url}")
    print("Press Ctrl+C to stop.")
    if args.open_browser:
        threading.Timer(0.25, lambda: __import__("webbrowser").open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
