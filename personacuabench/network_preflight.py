"""Read-only, task-independent network preflight for OSWorld guests.

The preflight is deliberately separate from task execution and scoring.  It
accepts an explicit set of target and control endpoints, builds a self-contained
stdlib-only Python probe for ``controller.run_python_script``, and normalizes the
controller response into a persistable JSON document.

No task object is accepted or modified.  In particular, an
``infeasible_candidate`` result is evidence for a later policy decision; it does
not rewrite the source task, its rubrics, or its raw score.
"""

from __future__ import annotations

import datetime as dt
import ipaddress
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence
from urllib.parse import urlsplit

from personacuabench.core import atomic_write_json


SCHEMA_VERSION = "persona-cua-network-preflight/v1"
GUEST_PAYLOAD_VERSION = "persona-cua-network-probe/v1"
OUTPUT_SENTINEL = "__ODYSSEY_NETWORK_PREFLIGHT_V1__"
PREFLIGHT_PHASE = "after_reset_before_agent"
EVIDENCE_SCOPE = "same_run"
RUBRIC_MAPPING_SEMANTICS = "exclusive_blocking_dependency"

EndpointRole = Literal["target", "control"]

CLASSIFICATION_STATUSES = frozenset(
    {
        "feasible",
        "target_external_unavailable",
        "general_dns_failure",
        "general_network_failure",
        "target_http_blocked",
        "target_timeout",
        "target_tls_failure",
        "target_connection_failure",
        "target_http_error",
        "indeterminate",
        "preflight_error",
    }
)

HTTP_STATUSES = frozenset(
    {
        "reachable",
        "blocked",
        "auth_required",
        "not_found",
        "client_error",
        "server_error",
        "dns_error",
        "timeout",
        "tls_error",
        "proxy_error",
        "connection_error",
        "transport_error",
        "unknown",
        "not_run",
    }
)

_KEY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
_ALLOWED_DIAGNOSTIC_HEADERS = frozenset(
    {
        "server",
        "via",
        "cf-ray",
        "cf-mitigated",
        "x-cache",
        "x-cache-hits",
        "x-sucuri-id",
        "x-sucuri-block",
        "x-akamai-transformed",
        "x-denied-reason",
        "retry-after",
    }
)
_TLS_ERROR_NAMES = frozenset(
    {"SSLError", "SSLCertVerificationError", "CertificateError"}
)
_CONNECTION_ERROR_NAMES = frozenset(
    {
        "ConnectionAbortedError",
        "ConnectionRefusedError",
        "ConnectionResetError",
        "RemoteDisconnected",
    }
)


class PreflightConfigurationError(ValueError):
    """Raised when endpoint definitions cannot support a sound comparison."""


class PreflightResultError(ValueError):
    """Raised when a normalized preflight document is not persistable."""


@dataclass(frozen=True)
class PreflightEndpoint:
    """One public endpoint checked by the guest preflight.

    At least one target and two distinct controls are required.  Two controls
    prevent a single unrelated outage from being mislabeled as a task-specific
    failure.
    """

    key: str
    role: EndpointRole
    url: str
    label: str | None = None
    affected_rubric_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _KEY_PATTERN.fullmatch(self.key):
            raise PreflightConfigurationError(
                "endpoint key must match [A-Za-z0-9][A-Za-z0-9_.-]{0,63}: "
                f"{self.key!r}"
            )
        if self.role not in {"target", "control"}:
            raise PreflightConfigurationError(
                f"endpoint {self.key!r} has invalid role {self.role!r}"
            )
        parsed = urlsplit(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise PreflightConfigurationError(
                f"endpoint {self.key!r} must use an absolute HTTP(S) URL"
            )
        if parsed.username is not None or parsed.password is not None:
            raise PreflightConfigurationError(
                f"endpoint {self.key!r} URL must not contain credentials"
            )
        expected_port = 443 if parsed.scheme == "https" else 80
        if parsed.port not in {None, expected_port}:
            raise PreflightConfigurationError(
                f"endpoint {self.key!r} must use a default HTTP(S) port"
            )
        host = (parsed.hostname or "").rstrip(".").lower()
        if "%" in host or host in {"localhost", "localhost.localdomain"} or host.endswith(
            (".localhost", ".local", ".internal")
        ):
            raise PreflightConfigurationError(
                f"endpoint {self.key!r} must not address a local host"
            )
        try:
            literal_address = ipaddress.ip_address(host)
        except ValueError:
            literal_address = None
        if literal_address is not None and not literal_address.is_global:
            raise PreflightConfigurationError(
                f"endpoint {self.key!r} must not address a non-public IP"
            )
        if self.label is not None and not self.label.strip():
            raise PreflightConfigurationError(
                f"endpoint {self.key!r} label must be non-empty when present"
            )
        if any(not re.fullmatch(r"R\d+", value) for value in self.affected_rubric_ids):
            raise PreflightConfigurationError(
                f"endpoint {self.key!r} has an invalid affected rubric id"
            )
        if len(set(self.affected_rubric_ids)) != len(self.affected_rubric_ids):
            raise PreflightConfigurationError(
                f"endpoint {self.key!r} has duplicate affected rubric ids"
            )
        if self.role == "control" and self.affected_rubric_ids:
            raise PreflightConfigurationError(
                f"control endpoint {self.key!r} cannot affect task rubrics"
            )

    @property
    def host(self) -> str:
        host = urlsplit(self.url).hostname
        assert host is not None
        return host.rstrip(".").lower()

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "role": self.role,
            "url": self.url,
            "host": self.host,
            "label": self.label,
            "affected_rubric_ids": list(self.affected_rubric_ids),
        }


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_run_context(task_id: str, run_id: str) -> tuple[str, str]:
    if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-f]{40}", task_id):
        raise PreflightConfigurationError(f"invalid task_id: {task_id!r}")
    if (
        not isinstance(run_id, str)
        or not run_id.strip()
        or len(run_id) > 255
        or any(ord(character) < 32 for character in run_id)
    ):
        raise PreflightConfigurationError("run_id must be a non-empty safe string")
    return task_id, run_id


def normalize_endpoints(
    endpoints: Sequence[PreflightEndpoint | Mapping[str, Any]],
) -> tuple[PreflightEndpoint, ...]:
    """Validate endpoints without retaining or modifying the caller's objects."""
    normalized: list[PreflightEndpoint] = []
    for item in endpoints:
        if isinstance(item, PreflightEndpoint):
            endpoint = item
        elif isinstance(item, Mapping):
            try:
                endpoint = PreflightEndpoint(
                    key=str(item["key"]),
                    role=str(item["role"]),  # type: ignore[arg-type]
                    url=str(item["url"]),
                    label=(
                        str(item["label"])
                        if item.get("label") is not None
                        else None
                    ),
                    affected_rubric_ids=tuple(
                        str(value)
                        for value in item.get("affected_rubric_ids", ())
                    ),
                )
            except KeyError as exc:
                raise PreflightConfigurationError(
                    f"endpoint is missing required field {exc.args[0]!r}"
                ) from exc
        else:
            raise PreflightConfigurationError(
                f"endpoint must be an object, got {type(item).__name__}"
            )
        normalized.append(endpoint)

    if not normalized:
        raise PreflightConfigurationError("at least one endpoint is required")
    keys = [endpoint.key for endpoint in normalized]
    if len(set(keys)) != len(keys):
        raise PreflightConfigurationError("endpoint keys must be unique")

    targets = [endpoint for endpoint in normalized if endpoint.role == "target"]
    controls = [endpoint for endpoint in normalized if endpoint.role == "control"]
    if not targets:
        raise PreflightConfigurationError("at least one target endpoint is required")
    if len({endpoint.host for endpoint in controls}) < 2:
        raise PreflightConfigurationError(
            "at least two controls on distinct hosts are required"
        )
    target_hosts = {endpoint.host for endpoint in targets}
    control_hosts = {endpoint.host for endpoint in controls}
    overlap = target_hosts & control_hosts
    if overlap:
        raise PreflightConfigurationError(
            "target and control hosts must be distinct: " + ", ".join(sorted(overlap))
        )
    return tuple(normalized)


def build_guest_probe_script(
    endpoints: Sequence[PreflightEndpoint | Mapping[str, Any]],
    *,
    task_id: str,
    run_id: str,
    timeout_seconds: float = 4.0,
    dns_attempts: int = 2,
) -> str:
    """Build the stdlib-only script passed to ``run_python_script``.

    DNS and HTTP work runs concurrently across endpoints.  The HTTP request is
    a GET with a one-byte range and the response body is never consumed.  The
    script writes no files and emits exactly one sentinel-prefixed JSON payload.
    """
    normalized = normalize_endpoints(endpoints)
    task_id, run_id = _validate_run_context(task_id, run_id)
    if not isinstance(timeout_seconds, (int, float)) or isinstance(
        timeout_seconds, bool
    ):
        raise PreflightConfigurationError("timeout_seconds must be numeric")
    timeout = float(timeout_seconds)
    if not math.isfinite(timeout) or not 1.0 <= timeout <= 10.0:
        raise PreflightConfigurationError(
            "timeout_seconds must be finite and between 1 and 10"
        )
    if isinstance(dns_attempts, bool) or not isinstance(dns_attempts, int):
        raise PreflightConfigurationError("dns_attempts must be an integer")
    if not 2 <= dns_attempts <= 4:
        raise PreflightConfigurationError("dns_attempts must be between 2 and 4")

    endpoint_json = json.dumps(
        [endpoint.to_dict() for endpoint in normalized],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    allowed_headers_json = json.dumps(sorted(_ALLOWED_DIAGNOSTIC_HEADERS))

    # Keep this source self-contained: OSWorld executes it in the guest from a
    # temporary file, where importing the local personacuabench package is impossible.
    return f'''from __future__ import annotations

import datetime
import ipaddress
import json
import multiprocessing
import os
import signal
import socket
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

ENDPOINTS = json.loads({endpoint_json!r})
TIMEOUT_SECONDS = {timeout!r}
GLOBAL_TIMEOUT_SECONDS = 20.0
DNS_JOB_TIMEOUT_SECONDS = 3.0
HTTP_JOB_TIMEOUT_SECONDS = 6.0
DNS_ATTEMPTS = {dns_attempts!r}
PAYLOAD_VERSION = {GUEST_PAYLOAD_VERSION!r}
SENTINEL = {OUTPUT_SENTINEL!r}
TASK_ID = {task_id!r}
RUN_ID = {run_id!r}
PHASE = {PREFLIGHT_PHASE!r}
EVIDENCE_SCOPE = {EVIDENCE_SCOPE!r}
ALLOWED_HEADERS = set(json.loads({allowed_headers_json!r}))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # A redirect response is sufficient for reachability and following it could
    # both exceed OSWorld's 30-second controller budget and cross a trust boundary.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


urllib.request.install_opener(urllib.request.build_opener(NoRedirect()))


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def clean_error(value):
    return " ".join(str(value).split())[:500]


def dns_attempt(host, port):
    started = time.monotonic()
    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        addresses = sorted({{record[4][0] for record in records if record[4]}})
        return {{
            "ok": bool(addresses),
            "addresses": addresses,
            "error_type": None,
            "error": None,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        }}
    except Exception as exc:
        return {{
            "ok": False,
            "addresses": [],
            "error_type": type(exc).__name__,
            "error": clean_error(exc),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        }}


def aggregate_dns(attempts):
    addresses = set()
    for attempt in attempts:
        addresses.update(attempt["addresses"])
    failures = [attempt for attempt in attempts if not attempt["ok"]]
    last_failure = failures[-1] if failures else {{}}
    return {{
        "ok": bool(addresses),
        "addresses": sorted(addresses),
        "attempts": attempts,
        "error_type": last_failure.get("error_type"),
        "error": last_failure.get("error"),
        "elapsed_ms": round(sum(attempt["elapsed_ms"] for attempt in attempts), 3),
    }}


def default_route_probe():
    errors = []
    try:
        with open("/proc/net/route", "r", encoding="ascii", errors="replace") as stream:
            for line in stream:
                fields = line.split()
                if len(fields) >= 4 and fields[1] == "00000000":
                    try:
                        if int(fields[3], 16) & 1:
                            return {{"default_route_present": True, "error": None}}
                    except ValueError:
                        continue
    except Exception as exc:
        errors.append(clean_error(exc))
    try:
        with open("/proc/net/ipv6_route", "r", encoding="ascii", errors="replace") as stream:
            for line in stream:
                fields = line.split()
                if len(fields) >= 10 and fields[0] == "0" * 32 and fields[1] == "00":
                    return {{"default_route_present": True, "error": None}}
    except Exception as exc:
        errors.append(clean_error(exc))
    return {{
        "default_route_present": False,
        "error": "; ".join(errors)[:500] or None,
    }}


def selected_headers(headers):
    selected = {{}}
    if headers is None:
        return selected
    for name, value in headers.items():
        lowered = str(name).lower()
        if lowered in ALLOWED_HEADERS:
            selected[lowered] = clean_error(value)
    return selected


def http_probe(url):
    started = time.monotonic()
    request = urllib.request.Request(
        url,
        headers={{
            "User-Agent": "PersonaCUABench-NetworkPreflight/1.0",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Range": "bytes=0-0",
        }},
        method="GET",
    )
    try:
        response = urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS)
        try:
            status_code = int(response.getcode())
            final_host = (urlsplit(response.geturl()).hostname or "").lower() or None
            headers = selected_headers(response.headers)
        finally:
            response.close()
        return {{
            "response_received": True,
            "status_code": status_code,
            "final_host": final_host,
            "headers": headers,
            "error_type": None,
            "error": None,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        }}
    except urllib.error.HTTPError as exc:
        try:
            final_host = (urlsplit(exc.geturl()).hostname or "").lower() or None
        except Exception:
            final_host = None
        try:
            exc.close()
        except Exception:
            pass
        return {{
            "response_received": True,
            "status_code": int(exc.code),
            "final_host": final_host,
            "headers": selected_headers(exc.headers),
            "error_type": "HTTPError",
            "error": clean_error(exc),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        }}
    except Exception as exc:
        reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
        return {{
            "response_received": False,
            "status_code": None,
            "final_host": None,
            "headers": {{}},
            "error_type": type(reason).__name__,
            "error": clean_error(reason),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        }}


def skipped_http(error_type, error):
    return {{
        "response_received": False,
        "status_code": None,
        "final_host": None,
        "headers": {{}},
        "error_type": error_type,
        "error": error,
        "elapsed_ms": 0.0,
    }}


def endpoint_port(endpoint):
    parsed = urlsplit(endpoint["url"])
    return parsed.port or (443 if parsed.scheme == "https" else 80)


def isolated_job(kind, endpoint, connection):
    try:
        if kind == "dns":
            value = dns_attempt(endpoint["host"], endpoint_port(endpoint))
        elif kind == "http":
            value = http_probe(endpoint["url"])
        else:
            raise ValueError("unknown probe job")
        connection.send({{"value": value, "worker_error": None}})
    except BaseException as exc:
        try:
            connection.send({{
                "value": None,
                "worker_error": type(exc).__name__ + ": " + clean_error(exc),
            }})
        except Exception:
            pass
    finally:
        connection.close()


def run_isolated_jobs(endpoints, kind, deadline_seconds):
    # libc DNS and parts of urllib cannot be interrupted safely in a thread.
    # One forked worker per endpoint lets the parent preserve all completed
    # results and terminate only the slow operation before OSWorld's 30s cap.
    context = multiprocessing.get_context("fork")
    jobs = {{}}
    for endpoint in endpoints:
        receive, send = context.Pipe(duplex=False)
        process = context.Process(
            target=isolated_job,
            args=(kind, endpoint, send),
        )
        process.start()
        send.close()
        jobs[endpoint["key"]] = {{
            "process": process,
            "receive": receive,
        }}

    results = {{}}
    deadline = time.monotonic() + deadline_seconds
    pending = set(jobs)
    while pending and time.monotonic() < deadline:
        for key in list(pending):
            job = jobs[key]
            connection = job["receive"]
            process = job["process"]
            if connection.poll():
                try:
                    results[key] = connection.recv()
                except (EOFError, OSError) as exc:
                    results[key] = {{"value": None, "worker_error": clean_error(exc)}}
                pending.remove(key)
                process.join(timeout=0.1)
                connection.close()
            elif not process.is_alive():
                results[key] = {{
                    "value": None,
                    "worker_error": "worker exited without a result",
                }}
                pending.remove(key)
                process.join(timeout=0.1)
                connection.close()
        if pending:
            time.sleep(0.02)

    for key in list(pending):
        job = jobs[key]
        process = job["process"]
        if process.is_alive():
            process.terminate()
        process.join(timeout=0.5)
        job["receive"].close()
        results[key] = {{
            "value": None,
            "worker_error": "job exceeded hard deadline",
        }}
    return results


def failed_dns_attempt(error_type, error, elapsed_ms):
    return {{
        "ok": False,
        "addresses": [],
        "error_type": error_type,
        "error": error,
        "elapsed_ms": elapsed_ms,
    }}


def collect_probes():
    attempts_by_key = {{endpoint["key"]: [] for endpoint in ENDPOINTS}}
    for attempt_index in range(DNS_ATTEMPTS):
        results = run_isolated_jobs(ENDPOINTS, "dns", DNS_JOB_TIMEOUT_SECONDS)
        for endpoint in ENDPOINTS:
            result = results[endpoint["key"]]
            value = result.get("value")
            if isinstance(value, dict):
                attempt = value
            else:
                worker_error = result.get("worker_error") or "DNS worker failed"
                error_type = (
                    "EndpointTimeout"
                    if "hard deadline" in worker_error
                    else "WorkerError"
                )
                attempt = failed_dns_attempt(
                    error_type,
                    worker_error,
                    DNS_JOB_TIMEOUT_SECONDS * 1000.0,
                )
            attempts_by_key[endpoint["key"]].append(attempt)
        if attempt_index + 1 < DNS_ATTEMPTS:
            time.sleep(0.2)

    dns_by_key = {{
        endpoint["key"]: aggregate_dns(attempts_by_key[endpoint["key"]])
        for endpoint in ENDPOINTS
    }}
    safe_http_endpoints = []
    unsafe_keys = set()
    for endpoint in ENDPOINTS:
        dns = dns_by_key[endpoint["key"]]
        if not dns["ok"]:
            continue
        try:
            public = bool(dns["addresses"]) and all(
                ipaddress.ip_address(value).is_global for value in dns["addresses"]
            )
        except ValueError:
            public = False
        if public:
            safe_http_endpoints.append(endpoint)
        else:
            unsafe_keys.add(endpoint["key"])

    http_results = run_isolated_jobs(
        safe_http_endpoints,
        "http",
        HTTP_JOB_TIMEOUT_SECONDS,
    ) if safe_http_endpoints else {{}}

    probes = []
    for endpoint in ENDPOINTS:
        key = endpoint["key"]
        dns = dns_by_key[key]
        policy_error = None
        if key in unsafe_keys:
            http = skipped_http(
                "UnsafeAddress",
                "HTTP skipped because DNS returned a non-public address",
            )
            policy_error = "non_public_dns_address"
        elif not dns["ok"]:
            http = skipped_http(
                "DNSUnresolved",
                "HTTP skipped because DNS did not resolve",
            )
        else:
            result = http_results[key]
            value = result.get("value")
            if isinstance(value, dict):
                http = value
            else:
                worker_error = result.get("worker_error") or "HTTP worker failed"
                error_type = (
                    "EndpointTimeout"
                    if "hard deadline" in worker_error
                    else "WorkerError"
                )
                http = skipped_http(error_type, worker_error)
        probes.append({{
            "key": key,
            "role": endpoint["role"],
            "url": endpoint["url"],
            "host": endpoint["host"],
            "dns": dns,
            "http": http,
            "policy_error": policy_error,
        }})
    return probes


started_at = utc_now()


def global_timeout_handler(_signum, _frame):
    # OSWorld's guest endpoint kills the entire script after 30 seconds.  Emit a
    # parseable, fail-closed payload first so a slow libc resolver cannot erase
    # all diagnostic evidence or be mistaken for infeasibility.
    payload = {{
        "probe_payload_version": PAYLOAD_VERSION,
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "phase": PHASE,
        "evidence_scope": EVIDENCE_SCOPE,
        "started_at": started_at,
        "finished_at": utc_now(),
        "timeout_seconds": TIMEOUT_SECONDS,
        "dns_attempts": DNS_ATTEMPTS,
        "network": {{
            "default_route_present": None,
            "error": "guest probe exceeded the 20-second global budget",
        }},
        "probes": [],
    }}
    print(SENTINEL + json.dumps(payload, ensure_ascii=True, separators=(",", ":")), flush=True)
    os._exit(0)


def main():
    signal.signal(signal.SIGALRM, global_timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, GLOBAL_TIMEOUT_SECONDS)
    socket.setdefaulttimeout(TIMEOUT_SECONDS)
    network = default_route_probe()
    probes = collect_probes()
    signal.setitimer(signal.ITIMER_REAL, 0.0)
    payload = {{
        "probe_payload_version": PAYLOAD_VERSION,
        "task_id": TASK_ID,
        "run_id": RUN_ID,
        "phase": PHASE,
        "evidence_scope": EVIDENCE_SCOPE,
        "started_at": started_at,
        "finished_at": utc_now(),
        "timeout_seconds": TIMEOUT_SECONDS,
        "dns_attempts": DNS_ATTEMPTS,
        "network": network,
        "probes": probes,
    }}
    print(SENTINEL + json.dumps(payload, ensure_ascii=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
'''


def run_network_preflight(
    controller: Any,
    endpoints: Sequence[PreflightEndpoint | Mapping[str, Any]],
    *,
    task_id: str,
    run_id: str,
    timeout_seconds: float = 4.0,
    dns_attempts: int = 2,
) -> dict[str, Any]:
    """Run the probe through an OSWorld controller and normalize its response."""
    normalized = normalize_endpoints(endpoints)
    script = build_guest_probe_script(
        normalized,
        task_id=task_id,
        run_id=run_id,
        timeout_seconds=timeout_seconds,
        dns_attempts=dns_attempts,
    )
    method = getattr(controller, "run_python_script", None)
    if not callable(method):
        raise PreflightConfigurationError(
            "controller does not provide run_python_script"
        )
    raw_result = method(script)
    return parse_controller_result(
        normalized,
        raw_result,
        task_id=task_id,
        run_id=run_id,
    )


def _clean_string(value: Any, *, limit: int = 500) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned[:limit] or None


def _coerce_number(value: Any, *, minimum: float = 0.0) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= minimum else None


def _normalize_dns(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {
            "status": "unknown",
            "addresses": [],
            "attempt_count": 0,
            "successful_attempts": 0,
            "all_attempts_unresolved": False,
            "elapsed_ms": None,
            "error_type": None,
            "error": "missing DNS result",
        }

    addresses: list[str] = []
    raw_addresses = raw.get("addresses")
    if isinstance(raw_addresses, list):
        for value in raw_addresses:
            if not isinstance(value, str):
                continue
            try:
                address = str(ipaddress.ip_address(value.strip()))
            except ValueError:
                continue
            if address not in addresses:
                addresses.append(address)
    addresses.sort()

    attempt_count = 0
    successful_attempts = 0
    negative_attempts = 0
    raw_attempts = raw.get("attempts")
    if isinstance(raw_attempts, list):
        for attempt in raw_attempts:
            if not isinstance(attempt, Mapping):
                continue
            attempt_count += 1
            attempt_addresses = attempt.get("addresses")
            if attempt.get("ok") is True and isinstance(attempt_addresses, list):
                valid_address = False
                for value in attempt_addresses:
                    if not isinstance(value, str):
                        continue
                    try:
                        ipaddress.ip_address(value.strip())
                    except ValueError:
                        continue
                    valid_address = True
                    break
                if valid_address:
                    successful_attempts += 1
            elif attempt.get("error_type") in {"gaierror", "herror"}:
                negative_attempts += 1
    elif addresses:
        # Legacy/synthetic payloads without per-attempt data remain useful for
        # diagnostics, but can never satisfy the repeated-failure gate.
        attempt_count = 1
        successful_attempts = 1

    error_type = _clean_string(raw.get("error_type"), limit=100)
    error = _clean_string(raw.get("error"))
    if addresses:
        status = "resolved"
    elif error_type in {"gaierror", "herror"}:
        status = "unresolved"
    elif raw.get("ok") is False:
        status = "resolver_error"
    else:
        status = "unresolved"
    return {
        "status": status,
        "addresses": addresses,
        "attempt_count": attempt_count,
        "successful_attempts": successful_attempts,
        "all_attempts_unresolved": (
            attempt_count >= 2
            and successful_attempts == 0
            and negative_attempts == attempt_count
            and not addresses
        ),
        "elapsed_ms": _coerce_number(raw.get("elapsed_ms")),
        "error_type": error_type,
        "error": error,
    }


def _diagnostic_headers(raw: Any) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    result: dict[str, str] = {}
    for key, value in raw.items():
        lowered = str(key).strip().lower()
        if lowered not in _ALLOWED_DIAGNOSTIC_HEADERS:
            continue
        cleaned = _clean_string(value)
        if cleaned is not None:
            result[lowered] = cleaned
    return result


def _block_signals(status_code: int | None, headers: Mapping[str, str]) -> list[str]:
    signals: list[str] = []
    if status_code in {403, 407, 429, 451}:
        signals.append(f"http_status_{status_code}")
    if headers.get("cf-mitigated", "").lower() == "challenge":
        signals.append("cloudflare_challenge")
    if "cf-ray" in headers and status_code in {403, 429, 503}:
        signals.append("cloudflare_edge_block")
    if "x-sucuri-block" in headers:
        signals.append("sucuri_block")
    if "x-denied-reason" in headers:
        signals.append("explicit_denial_header")
    if "retry-after" in headers and status_code in {429, 503}:
        signals.append("rate_or_service_limit")
    return signals


def _normalize_http(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {
            "status": "not_run",
            "response_received": False,
            "status_code": None,
            "final_host": None,
            "elapsed_ms": None,
            "diagnostic_headers": {},
            "block_signals": [],
            "error_type": None,
            "error": "missing HTTP result",
        }

    response_received = raw.get("response_received") is True
    code_value = raw.get("status_code")
    status_code = (
        int(code_value)
        if isinstance(code_value, int)
        and not isinstance(code_value, bool)
        and 100 <= code_value <= 599
        else None
    )
    headers = _diagnostic_headers(raw.get("headers"))
    block_signals = _block_signals(status_code, headers)
    error_type = _clean_string(raw.get("error_type"), limit=100)
    error = _clean_string(raw.get("error"))
    combined_error = " ".join(part for part in (error_type, error) if part).lower()

    if response_received and status_code is not None:
        if 200 <= status_code <= 399:
            status = "reachable"
        elif block_signals:
            status = "blocked"
        elif status_code == 401:
            status = "auth_required"
        elif status_code in {404, 410}:
            status = "not_found"
        elif 400 <= status_code <= 499:
            status = "client_error"
        elif 500 <= status_code <= 599:
            status = "server_error"
        else:
            status = "unknown"
    elif error_type in {"gaierror", "herror"} or "name or service not known" in combined_error:
        status = "dns_error"
    elif error_type in {"TimeoutError", "timeout", "EndpointTimeout"} or (
        "timed out" in combined_error or "hard deadline" in combined_error
    ):
        status = "timeout"
    elif error_type in _TLS_ERROR_NAMES or any(
        token in combined_error
        for token in ("certificate verify failed", "ssl:", "tls")
    ):
        status = "tls_error"
    elif "proxy" in combined_error or "tunnel connection failed" in combined_error:
        status = "proxy_error"
    elif error_type in _CONNECTION_ERROR_NAMES or any(
        token in combined_error
        for token in ("connection refused", "connection reset", "network is unreachable")
    ):
        status = "connection_error"
    elif error_type or error:
        status = "transport_error"
    else:
        status = "unknown"

    final_host = _clean_string(raw.get("final_host"), limit=253)
    return {
        "status": status,
        "response_received": response_received,
        "status_code": status_code,
        "final_host": final_host,
        "elapsed_ms": _coerce_number(raw.get("elapsed_ms")),
        "diagnostic_headers": headers,
        "block_signals": block_signals,
        "error_type": error_type,
        "error": error,
    }


def _empty_probe(endpoint: PreflightEndpoint, error: str) -> dict[str, Any]:
    return {
        "endpoint": endpoint.to_dict(),
        "dns": _normalize_dns(None),
        "http": _normalize_http(None),
        "probe_error": error,
    }


def _normalize_probe(
    endpoint: PreflightEndpoint, raw: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "endpoint": endpoint.to_dict(),
        "dns": _normalize_dns(raw.get("dns")),
        "http": _normalize_http(raw.get("http")),
        "probe_error": _clean_string(raw.get("policy_error")),
    }


def _normalize_network(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {
            "default_route_present": None,
            "error": "guest omitted default-route result",
        }
    route = raw.get("default_route_present")
    return {
        "default_route_present": route if isinstance(route, bool) else None,
        "error": _clean_string(raw.get("error")),
    }


def _control_summary(probes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    controls = [
        probe for probe in probes if probe["endpoint"]["role"] == "control"
    ]
    count = len(controls)
    quorum = max(2, count // 2 + 1)
    dns_resolved = sum(probe["dns"]["status"] == "resolved" for probe in controls)
    http_responded = sum(probe["http"]["response_received"] for probe in controls)
    http_reachable = sum(probe["http"]["status"] == "reachable" for probe in controls)
    healthy = sum(
        probe["dns"]["status"] == "resolved"
        and probe["http"]["status"] == "reachable"
        for probe in controls
    )
    return {
        "configured": count,
        "quorum": quorum,
        "dns_resolved": dns_resolved,
        "http_responded": http_responded,
        "http_reachable": http_reachable,
        "healthy": healthy,
        "dns_quorum": dns_resolved >= quorum,
        "http_quorum": http_responded >= quorum,
        "healthy_minimum_met": healthy >= 2,
    }


def _classification(
    probes: Sequence[Mapping[str, Any]],
    *,
    network: Mapping[str, Any],
    execution_ok: bool,
) -> dict[str, Any]:
    controls = _control_summary(probes)
    targets = [probe for probe in probes if probe["endpoint"]["role"] == "target"]
    target_dns = [probe["dns"]["status"] for probe in targets]
    target_http = [probe["http"]["status"] for probe in targets]
    target_responses = [probe["http"]["response_received"] for probe in targets]
    reason_codes: list[str] = []

    if not execution_ok or any(probe.get("probe_error") for probe in probes):
        status = "preflight_error"
        confidence = "low"
        reason_codes.append("probe_execution_incomplete")
    elif targets and all(value == "reachable" for value in target_http):
        status = "feasible"
        confidence = "high" if controls["http_quorum"] else "medium"
        reason_codes.append("all_targets_http_reachable")
    else:
        all_target_aliases_repeatedly_unresolved = bool(targets) and all(
            probe["dns"]["all_attempts_unresolved"]
            and not probe["http"]["response_received"]
            for probe in targets
        )
        target_dns_unavailable = any(
            dns != "resolved" and not response
            for dns, response in zip(target_dns, target_responses)
        )
        high_confidence_dns_gate = (
            all_target_aliases_repeatedly_unresolved
            and network.get("default_route_present") is True
            and controls["healthy_minimum_met"]
        )
        if high_confidence_dns_gate:
            status = "target_external_unavailable"
            confidence = "high"
            reason_codes.extend(
                [
                    "all_target_aliases_repeatedly_unresolved",
                    "default_route_present",
                    "two_healthy_controls",
                ]
            )
        elif target_dns_unavailable and network.get("default_route_present") is False:
            status = "general_network_failure"
            confidence = "high"
            reason_codes.append("default_route_missing")
        elif target_dns_unavailable and (
            controls["dns_quorum"] or controls["http_reachable"] > 0
        ):
            status = "target_external_unavailable"
            confidence = "medium"
            reason_codes.extend(
                ["target_dns_unavailable", "high_confidence_gate_not_met"]
            )
        elif target_dns_unavailable and controls["dns_resolved"] < controls["quorum"]:
            status = "general_dns_failure"
            confidence = "high" if controls["dns_resolved"] == 0 else "medium"
            reason_codes.append("target_and_control_dns_unavailable")
        elif "blocked" in target_http:
            status = "target_http_blocked"
            confidence = "high" if controls["http_quorum"] else "medium"
            reason_codes.append("target_returned_access_block_signal")
        elif "timeout" in target_http:
            if controls["http_responded"] == 0:
                status = "general_network_failure"
                reason_codes.append("target_and_controls_have_no_http_response")
            else:
                status = "target_timeout"
                reason_codes.append("target_timed_out_while_controls_responded")
            confidence = "high" if controls["http_quorum"] else "medium"
        elif "tls_error" in target_http:
            status = "target_tls_failure"
            confidence = "high" if controls["http_quorum"] else "medium"
            reason_codes.append("target_tls_failed")
        elif any(
            value in {"connection_error", "proxy_error", "transport_error"}
            for value in target_http
        ):
            if controls["http_responded"] == 0:
                status = "general_network_failure"
                reason_codes.append("no_endpoint_returned_http_response")
            else:
                status = "target_connection_failure"
                reason_codes.append("target_transport_failed_while_controls_responded")
            confidence = "high" if controls["http_quorum"] else "medium"
        elif "not_found" in target_http:
            status = "indeterminate"
            confidence = "medium"
            reason_codes.append("target_returned_not_found_http_result")
        elif any(
            value in {
                "auth_required",
                "client_error",
                "server_error",
            }
            for value in target_http
        ):
            status = "target_http_error"
            confidence = "high" if controls["http_quorum"] else "medium"
            reason_codes.append("target_returned_non_usable_http_status")
        elif controls["http_responded"] == 0:
            status = "general_network_failure"
            confidence = "medium"
            reason_codes.append("controls_have_no_http_response")
        else:
            status = "indeterminate"
            confidence = "low"
            reason_codes.append("insufficient_or_conflicting_evidence")

    infeasible_candidate = (
        status == "target_external_unavailable"
        and confidence == "high"
        and network.get("default_route_present") is True
        and controls["healthy_minimum_met"]
        and bool(targets)
        and all(
            probe["dns"]["all_attempts_unresolved"]
            and not probe["http"]["response_received"]
            for probe in targets
        )
    )
    if infeasible_candidate:
        reason_codes.append("target_specific_failure_with_healthy_controls")

    assessment_complete = status == "feasible" or infeasible_candidate

    return {
        "status": status,
        "confidence": confidence,
        "assessment_complete": assessment_complete,
        "infeasible_candidate": infeasible_candidate,
        "adjustment_eligibility": (
            "eligible_for_policy_review"
            if infeasible_candidate
            else "not_eligible_from_preflight"
        ),
        "raw_score_affected": False,
        "reason_codes": reason_codes,
        "control_summary": controls,
    }


def _feasibility(
    classification: Mapping[str, Any], probes: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    candidate = classification.get("infeasible_candidate") is True
    if candidate:
        status = "infeasible_candidate"
        target_keys = [
            probe["endpoint"]["key"]
            for probe in probes
            if probe["endpoint"]["role"] == "target"
        ]
        affected = sorted(
            {
                rubric_id
                for probe in probes
                if probe["endpoint"]["role"] == "target"
                for rubric_id in probe["endpoint"]["affected_rubric_ids"]
            }
        )
    elif classification.get("status") == "feasible":
        status = "feasible"
        target_keys = []
        affected = []
    else:
        status = "indeterminate"
        target_keys = []
        affected = []
    return {
        "status": status,
        "affected_rubric_ids": affected,
        "affected_target_keys": target_keys,
        "raw_score_affected": False,
    }


def _policy(
    classification: Mapping[str, Any], probes: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    feasibility = _feasibility(classification, probes)
    return {
        "version": "dns-only-v1",
        "dns_only": True,
        "rubric_mapping_semantics": RUBRIC_MAPPING_SEMANTICS,
        "assessment_complete": classification.get("assessment_complete") is True,
        "adjustment_eligibility": classification.get("adjustment_eligibility"),
        "affected_rubric_ids": list(feasibility["affected_rubric_ids"]),
        "raw_score_affected": False,
    }


def _error_document(
    endpoints: Sequence[PreflightEndpoint],
    *,
    task_id: str,
    run_id: str,
    controller_status: str | None,
    return_code: int | None,
    error: str,
) -> dict[str, Any]:
    probes = [_empty_probe(endpoint, error) for endpoint in endpoints]
    network = _normalize_network(None)
    classification = _classification(
        probes,
        network=network,
        execution_ok=False,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "run_id": run_id,
        "phase": PREFLIGHT_PHASE,
        "evidence_scope": EVIDENCE_SCOPE,
        "observed_at": _utc_now(),
        "execution": {
            "status": "error",
            "controller_status": controller_status,
            "return_code": return_code,
            "error": error,
            "warnings": [],
        },
        "network": network,
        "classification": classification,
        "feasibility": _feasibility(classification, probes),
        "policy": _policy(classification, probes),
        "probes": probes,
    }


def parse_controller_result(
    endpoints: Sequence[PreflightEndpoint | Mapping[str, Any]],
    controller_result: Any,
    *,
    task_id: str,
    run_id: str,
) -> dict[str, Any]:
    """Parse an OSWorld ``run_python_script`` response into schema v1."""
    normalized = normalize_endpoints(endpoints)
    task_id, run_id = _validate_run_context(task_id, run_id)
    if not isinstance(controller_result, Mapping):
        return _error_document(
            normalized,
            task_id=task_id,
            run_id=run_id,
            controller_status=None,
            return_code=None,
            error="controller returned no structured result",
        )

    controller_status = _clean_string(controller_result.get("status"), limit=50)
    return_value = controller_result.get("return_code")
    return_code = (
        return_value
        if isinstance(return_value, int) and not isinstance(return_value, bool)
        else None
    )
    output = controller_result.get("output")
    if not isinstance(output, str):
        output = ""

    payload: Mapping[str, Any] | None = None
    warnings: list[str] = []
    for line in reversed(output.splitlines()):
        if not line.startswith(OUTPUT_SENTINEL):
            continue
        candidate = line[len(OUTPUT_SENTINEL) :]
        try:
            decoded = json.loads(candidate)
        except json.JSONDecodeError:
            warnings.append("malformed_sentinel_payload_ignored")
            continue
        if isinstance(decoded, Mapping):
            payload = decoded
            break

    if payload is None:
        detail = _clean_string(controller_result.get("error")) or (
            "guest output did not contain a valid preflight payload"
        )
        return _error_document(
            normalized,
            task_id=task_id,
            run_id=run_id,
            controller_status=controller_status,
            return_code=return_code,
            error=detail,
        )
    if payload.get("probe_payload_version") != GUEST_PAYLOAD_VERSION:
        return _error_document(
            normalized,
            task_id=task_id,
            run_id=run_id,
            controller_status=controller_status,
            return_code=return_code,
            error="unsupported guest preflight payload version",
        )
    if (
        payload.get("task_id") != task_id
        or payload.get("run_id") != run_id
        or payload.get("phase") != PREFLIGHT_PHASE
        or payload.get("evidence_scope") != EVIDENCE_SCOPE
    ):
        return _error_document(
            normalized,
            task_id=task_id,
            run_id=run_id,
            controller_status=controller_status,
            return_code=return_code,
            error="guest preflight context does not match this task/run/phase",
        )

    raw_probes = payload.get("probes")
    by_key: dict[str, Mapping[str, Any]] = {}
    if isinstance(raw_probes, list):
        for raw_probe in raw_probes:
            if not isinstance(raw_probe, Mapping):
                warnings.append("non_object_probe_ignored")
                continue
            key = raw_probe.get("key")
            if not isinstance(key, str):
                warnings.append("probe_without_key_ignored")
                continue
            if key in by_key:
                warnings.append(f"duplicate_probe_ignored:{key}")
                continue
            by_key[key] = raw_probe

    expected_keys = {endpoint.key for endpoint in normalized}
    for unexpected in sorted(set(by_key) - expected_keys):
        warnings.append(f"unexpected_probe_ignored:{unexpected}")

    probes: list[dict[str, Any]] = []
    for endpoint in normalized:
        raw_probe = by_key.get(endpoint.key)
        if raw_probe is None:
            probes.append(_empty_probe(endpoint, "guest omitted endpoint result"))
        else:
            probes.append(_normalize_probe(endpoint, raw_probe))

    execution_ok = (
        controller_status == "success"
        and return_code in {None, 0}
        and all(probe["probe_error"] is None for probe in probes)
    )
    observed_at = _clean_string(payload.get("finished_at"), limit=50) or _utc_now()
    network = _normalize_network(payload.get("network"))
    classification = _classification(
        probes,
        network=network,
        execution_ok=execution_ok,
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id,
        "run_id": run_id,
        "phase": PREFLIGHT_PHASE,
        "evidence_scope": EVIDENCE_SCOPE,
        "observed_at": observed_at,
        "execution": {
            "status": "complete" if execution_ok else "error",
            "controller_status": controller_status,
            "return_code": return_code,
            "error": (
                None
                if execution_ok
                else _clean_string(controller_result.get("error"))
                or "guest preflight execution was incomplete"
            ),
            "warnings": warnings,
        },
        "network": network,
        "classification": classification,
        "feasibility": _feasibility(classification, probes),
        "policy": _policy(classification, probes),
        "probes": probes,
    }
    validate_preflight_document(result)
    return result


def validate_preflight_document(document: Any) -> dict[str, Any]:
    """Validate structure *and* recompute every scoring-relevant summary.

    This mirrors ``network_preflight.schema.json`` without adding a runtime
    dependency on ``jsonschema``.  Recomputing classification, feasibility and
    policy from the persisted probes prevents a self-consistent SHA over a
    hand-authored summary from becoming score-eligible.
    """

    def exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise PreflightResultError(f"{label} must be an object")
        if set(value) != expected:
            raise PreflightResultError(f"{label} fields do not match the schema")
        return value

    def nullable_string(value: Any, label: str) -> None:
        if value is not None and not isinstance(value, str):
            raise PreflightResultError(f"{label} must be a string or null")

    def nonnegative_number(value: Any, label: str) -> None:
        if value is None:
            return
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            or float(value) < 0
        ):
            raise PreflightResultError(f"{label} must be a non-negative number or null")

    document = exact_keys(
        document,
        {
            "schema_version",
            "task_id",
            "run_id",
            "phase",
            "evidence_scope",
            "observed_at",
            "execution",
            "network",
            "classification",
            "feasibility",
            "policy",
            "probes",
        },
        "preflight document",
    )
    if document.get("schema_version") != SCHEMA_VERSION:
        raise PreflightResultError("unsupported preflight schema_version")
    try:
        _validate_run_context(document.get("task_id"), document.get("run_id"))
    except PreflightConfigurationError as exc:
        raise PreflightResultError(str(exc)) from exc
    if document.get("phase") != PREFLIGHT_PHASE:
        raise PreflightResultError("preflight phase is invalid")
    if document.get("evidence_scope") != EVIDENCE_SCOPE:
        raise PreflightResultError("preflight evidence_scope is invalid")
    if not isinstance(document.get("observed_at"), str) or not document[
        "observed_at"
    ].strip():
        raise PreflightResultError("observed_at must be a non-empty string")

    execution = exact_keys(
        document.get("execution"),
        {"status", "controller_status", "return_code", "error", "warnings"},
        "execution",
    )
    if execution.get("status") not in {"complete", "error"}:
        raise PreflightResultError("execution.status must be complete or error")
    nullable_string(execution.get("controller_status"), "execution.controller_status")
    return_code = execution.get("return_code")
    if return_code is not None and (
        isinstance(return_code, bool) or not isinstance(return_code, int)
    ):
        raise PreflightResultError("execution.return_code must be an integer or null")
    nullable_string(execution.get("error"), "execution.error")
    warnings = execution.get("warnings")
    if not isinstance(warnings, list) or any(
        not isinstance(value, str) for value in warnings
    ):
        raise PreflightResultError("execution.warnings must be a string array")
    if execution["status"] == "complete" and (
        execution.get("controller_status") != "success"
        or return_code not in {None, 0}
        or execution.get("error") is not None
    ):
        raise PreflightResultError("complete execution metadata is inconsistent")

    network = exact_keys(
        document.get("network"), {"default_route_present", "error"}, "network"
    )
    route = network.get("default_route_present")
    if route is not None and not isinstance(route, bool):
        raise PreflightResultError("network.default_route_present is invalid")
    nullable_string(network.get("error"), "network.error")

    probes_value = document.get("probes")
    if not isinstance(probes_value, list) or len(probes_value) < 3:
        raise PreflightResultError("probes must contain at least three entries")
    probes: list[dict[str, Any]] = []
    endpoint_objects: list[PreflightEndpoint] = []
    for index, raw_probe in enumerate(probes_value, start=1):
        probe = exact_keys(
            raw_probe, {"endpoint", "dns", "http", "probe_error"}, f"probe #{index}"
        )
        endpoint = exact_keys(
            probe.get("endpoint"),
            {"key", "role", "url", "host", "label", "affected_rubric_ids"},
            f"probe #{index} endpoint",
        )
        affected = endpoint.get("affected_rubric_ids")
        if not isinstance(affected, list) or any(
            not isinstance(value, str) for value in affected
        ):
            raise PreflightResultError(
                f"probe #{index} endpoint affected_rubric_ids is invalid"
            )
        nullable_string(endpoint.get("label"), f"probe #{index} endpoint.label")
        try:
            endpoint_object = PreflightEndpoint(
                key=endpoint.get("key"),
                role=endpoint.get("role"),
                url=endpoint.get("url"),
                label=endpoint.get("label"),
                affected_rubric_ids=tuple(affected),
            )
        except (PreflightConfigurationError, TypeError) as exc:
            raise PreflightResultError(f"probe #{index} endpoint is invalid: {exc}") from exc
        if endpoint.get("host") != endpoint_object.host:
            raise PreflightResultError(f"probe #{index} endpoint host is inconsistent")
        endpoint_objects.append(endpoint_object)

        dns = exact_keys(
            probe.get("dns"),
            {
                "status",
                "addresses",
                "attempt_count",
                "successful_attempts",
                "all_attempts_unresolved",
                "elapsed_ms",
                "error_type",
                "error",
            },
            f"probe #{index} DNS",
        )
        if dns.get("status") not in {
            "resolved",
            "unresolved",
            "resolver_error",
            "unknown",
        }:
            raise PreflightResultError(f"probe #{index} DNS status is invalid")
        addresses = dns.get("addresses")
        if not isinstance(addresses, list) or len(set(addresses)) != len(addresses):
            raise PreflightResultError(f"probe #{index} DNS addresses are invalid")
        for address in addresses:
            if not isinstance(address, str):
                raise PreflightResultError(f"probe #{index} DNS address is invalid")
            try:
                ipaddress.ip_address(address)
            except ValueError as exc:
                raise PreflightResultError(
                    f"probe #{index} DNS address is invalid"
                ) from exc
        for field in ("attempt_count", "successful_attempts"):
            value = dns.get(field)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise PreflightResultError(f"probe #{index} DNS {field} is invalid")
        if dns["successful_attempts"] > dns["attempt_count"]:
            raise PreflightResultError(f"probe #{index} DNS attempt counts conflict")
        if not isinstance(dns.get("all_attempts_unresolved"), bool):
            raise PreflightResultError(
                f"probe #{index} DNS all_attempts_unresolved is invalid"
            )
        expected_unresolved = (
            dns["attempt_count"] >= 2
            and dns["successful_attempts"] == 0
            and not addresses
            and dns["status"] == "unresolved"
        )
        if dns["all_attempts_unresolved"] is not expected_unresolved:
            raise PreflightResultError(f"probe #{index} DNS summary is inconsistent")
        if (dns["status"] == "resolved") is not bool(addresses):
            raise PreflightResultError(f"probe #{index} DNS status/address mismatch")
        nonnegative_number(dns.get("elapsed_ms"), f"probe #{index} DNS elapsed_ms")
        nullable_string(dns.get("error_type"), f"probe #{index} DNS error_type")
        nullable_string(dns.get("error"), f"probe #{index} DNS error")

        http = exact_keys(
            probe.get("http"),
            {
                "status",
                "response_received",
                "status_code",
                "final_host",
                "elapsed_ms",
                "diagnostic_headers",
                "block_signals",
                "error_type",
                "error",
            },
            f"probe #{index} HTTP",
        )
        if http.get("status") not in HTTP_STATUSES:
            raise PreflightResultError(f"probe #{index} HTTP status is invalid")
        if not isinstance(http.get("response_received"), bool):
            raise PreflightResultError(f"probe #{index} HTTP response flag is invalid")
        status_code = http.get("status_code")
        if status_code is not None and (
            isinstance(status_code, bool)
            or not isinstance(status_code, int)
            or not 100 <= status_code <= 599
        ):
            raise PreflightResultError(f"probe #{index} HTTP status code is invalid")
        if http["response_received"] is not (status_code is not None):
            raise PreflightResultError(f"probe #{index} HTTP response/code mismatch")
        if http["status"] == "reachable" and not (
            http["response_received"] and 200 <= status_code <= 399
        ):
            raise PreflightResultError(f"probe #{index} HTTP reachable state is invalid")
        nonnegative_number(http.get("elapsed_ms"), f"probe #{index} HTTP elapsed_ms")
        nullable_string(http.get("final_host"), f"probe #{index} HTTP final_host")
        nullable_string(http.get("error_type"), f"probe #{index} HTTP error_type")
        nullable_string(http.get("error"), f"probe #{index} HTTP error")
        headers = http.get("diagnostic_headers")
        if not isinstance(headers, dict) or any(
            key not in _ALLOWED_DIAGNOSTIC_HEADERS or not isinstance(value, str)
            for key, value in headers.items()
        ):
            raise PreflightResultError(f"probe #{index} HTTP headers are invalid")
        signals = http.get("block_signals")
        if not isinstance(signals, list) or any(
            not isinstance(value, str) for value in signals
        ):
            raise PreflightResultError(f"probe #{index} HTTP block signals are invalid")
        nullable_string(probe.get("probe_error"), f"probe #{index} probe_error")
        probes.append(probe)

    try:
        normalize_endpoints(endpoint_objects)
    except PreflightConfigurationError as exc:
        raise PreflightResultError(f"persisted endpoints are invalid: {exc}") from exc
    if execution["status"] == "complete" and any(
        probe.get("probe_error") is not None for probe in probes
    ):
        raise PreflightResultError("complete execution cannot contain probe errors")

    classification = exact_keys(
        document.get("classification"),
        {
            "status",
            "confidence",
            "assessment_complete",
            "infeasible_candidate",
            "adjustment_eligibility",
            "raw_score_affected",
            "reason_codes",
            "control_summary",
        },
        "classification",
    )
    if classification.get("status") not in CLASSIFICATION_STATUSES:
        raise PreflightResultError("classification.status is invalid")
    if classification.get("confidence") not in {"high", "medium", "low"}:
        raise PreflightResultError("classification.confidence is invalid")
    for field in ("assessment_complete", "infeasible_candidate"):
        if not isinstance(classification.get(field), bool):
            raise PreflightResultError(f"classification.{field} is invalid")
    if classification.get("adjustment_eligibility") not in {
        "eligible_for_policy_review",
        "not_eligible_from_preflight",
    }:
        raise PreflightResultError("classification.adjustment_eligibility is invalid")
    if classification.get("raw_score_affected") is not False:
        raise PreflightResultError("preflight must not alter the raw score")
    reasons = classification.get("reason_codes")
    if not isinstance(reasons, list) or any(not isinstance(value, str) for value in reasons):
        raise PreflightResultError("classification.reason_codes is invalid")
    controls = exact_keys(
        classification.get("control_summary"),
        {
            "configured",
            "quorum",
            "dns_resolved",
            "http_responded",
            "http_reachable",
            "healthy",
            "dns_quorum",
            "http_quorum",
            "healthy_minimum_met",
        },
        "classification.control_summary",
    )
    for field in (
        "configured",
        "quorum",
        "dns_resolved",
        "http_responded",
        "http_reachable",
        "healthy",
    ):
        value = controls.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise PreflightResultError(f"control_summary.{field} is invalid")
    for field in ("dns_quorum", "http_quorum", "healthy_minimum_met"):
        if not isinstance(controls.get(field), bool):
            raise PreflightResultError(f"control_summary.{field} is invalid")

    feasibility = exact_keys(
        document.get("feasibility"),
        {"status", "affected_rubric_ids", "affected_target_keys", "raw_score_affected"},
        "feasibility",
    )
    if feasibility.get("status") not in {
        "infeasible_candidate",
        "feasible",
        "indeterminate",
    }:
        raise PreflightResultError("feasibility.status is invalid")
    affected_ids = feasibility.get("affected_rubric_ids")
    if (
        not isinstance(affected_ids, list)
        or len(set(affected_ids)) != len(affected_ids)
        or any(
            not isinstance(value, str) or not re.fullmatch(r"R\d+", value)
            for value in affected_ids
        )
    ):
        raise PreflightResultError("feasibility.affected_rubric_ids is invalid")
    target_keys = feasibility.get("affected_target_keys")
    if (
        not isinstance(target_keys, list)
        or len(set(target_keys)) != len(target_keys)
        or any(not isinstance(value, str) or not value for value in target_keys)
    ):
        raise PreflightResultError("feasibility.affected_target_keys is invalid")
    if feasibility.get("raw_score_affected") is not False:
        raise PreflightResultError("feasibility must not alter the raw score")

    policy = exact_keys(
        document.get("policy"),
        {
            "version",
            "dns_only",
            "rubric_mapping_semantics",
            "assessment_complete",
            "adjustment_eligibility",
            "affected_rubric_ids",
            "raw_score_affected",
        },
        "policy",
    )
    if policy.get("version") != "dns-only-v1" or policy.get("dns_only") is not True:
        raise PreflightResultError("policy is invalid")
    if policy.get("rubric_mapping_semantics") != RUBRIC_MAPPING_SEMANTICS:
        raise PreflightResultError("policy rubric mapping semantics are invalid")
    if policy.get("raw_score_affected") is not False:
        raise PreflightResultError("policy must not alter the raw score")

    derived_classification = _classification(
        probes,
        network=network,
        execution_ok=execution["status"] == "complete",
    )
    derived_feasibility = _feasibility(derived_classification, probes)
    derived_policy = _policy(derived_classification, probes)
    if classification != derived_classification:
        raise PreflightResultError("classification does not match persisted probe evidence")
    if feasibility != derived_feasibility:
        raise PreflightResultError("feasibility does not match persisted probe evidence")
    if policy != derived_policy:
        raise PreflightResultError("policy does not match persisted probe evidence")
    return document


def write_preflight_document(path: Path, document: Mapping[str, Any]) -> None:
    """Validate and atomically persist a preflight document as JSON."""
    value = dict(document)
    validate_preflight_document(value)
    atomic_write_json(path, value)
