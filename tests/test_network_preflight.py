#!/usr/bin/env python3
"""Offline tests for the guest network preflight and its feasibility gate."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from personacuabench.availability import (
    load_task_preflight_endpoints,
    make_environment_preflight,
)
from personacuabench.core import ConfigurationError
from personacuabench.network_preflight import (
    GUEST_PAYLOAD_VERSION,
    OUTPUT_SENTINEL,
    PreflightConfigurationError,
    PreflightEndpoint,
    PreflightResultError,
    build_guest_probe_script,
    parse_controller_result,
    run_network_preflight,
    validate_preflight_document,
    write_preflight_document,
)


TASK_ID = "a" * 40
RUN_ID = "offline-network-preflight-run"


def _endpoints() -> list[PreflightEndpoint]:
    return [
        PreflightEndpoint(
            "target_apex",
            "target",
            "https://retired.invalid/",
            affected_rubric_ids=("R1",),
        ),
        PreflightEndpoint(
            "target_www",
            "target",
            "https://www.retired.invalid/",
            affected_rubric_ids=("R1",),
        ),
        PreflightEndpoint("control_one", "control", "https://example.com/"),
        PreflightEndpoint("control_two", "control", "https://www.python.org/"),
    ]


def _dns_resolved(address: str) -> dict[str, Any]:
    attempts = [
        {
            "ok": True,
            "addresses": [address],
            "error_type": None,
            "error": None,
            "elapsed_ms": 2.0,
        },
        {
            "ok": True,
            "addresses": [address],
            "error_type": None,
            "error": None,
            "elapsed_ms": 1.5,
        },
    ]
    return {
        "ok": True,
        "addresses": [address],
        "attempts": attempts,
        "error_type": None,
        "error": None,
        "elapsed_ms": 3.5,
    }


def _dns_unresolved() -> dict[str, Any]:
    attempts = [
        {
            "ok": False,
            "addresses": [],
            "error_type": "gaierror",
            "error": "[Errno -2] Name or service not known",
            "elapsed_ms": 3.0,
        },
        {
            "ok": False,
            "addresses": [],
            "error_type": "gaierror",
            "error": "[Errno -2] Name or service not known",
            "elapsed_ms": 2.5,
        },
    ]
    return {
        "ok": False,
        "addresses": [],
        "attempts": attempts,
        "error_type": "gaierror",
        "error": "[Errno -2] Name or service not known",
        "elapsed_ms": 5.5,
    }


def _http_response(
    status_code: int, *, headers: dict[str, str] | None = None
) -> dict[str, Any]:
    return {
        "response_received": True,
        "status_code": status_code,
        "final_host": "fixture.example",
        "headers": headers or {},
        "error_type": "HTTPError" if status_code >= 400 else None,
        "error": f"HTTP Error {status_code}" if status_code >= 400 else None,
        "elapsed_ms": 20.0,
    }


def _http_failure(error_type: str, error: str) -> dict[str, Any]:
    return {
        "response_received": False,
        "status_code": None,
        "final_host": None,
        "headers": {},
        "error_type": error_type,
        "error": error,
        "elapsed_ms": 25.0,
    }


def _probe(
    endpoint: PreflightEndpoint,
    *,
    dns: dict[str, Any],
    http: dict[str, Any],
) -> dict[str, Any]:
    return {
        "key": endpoint.key,
        "role": endpoint.role,
        "url": endpoint.url,
        "host": endpoint.host,
        "dns": dns,
        "http": http,
    }


def _healthy_controls(endpoints: list[PreflightEndpoint]) -> list[dict[str, Any]]:
    return [
        _probe(
            endpoints[2],
            dns=_dns_resolved("93.184.216.34"),
            http=_http_response(200),
        ),
        _probe(
            endpoints[3],
            dns=_dns_resolved("151.101.0.223"),
            http=_http_response(301),
        ),
    ]


def _payload(
    probes: list[dict[str, Any]],
    *,
    default_route: bool = True,
    task_id: str = TASK_ID,
    run_id: str = RUN_ID,
) -> dict[str, Any]:
    return {
        "probe_payload_version": GUEST_PAYLOAD_VERSION,
        "task_id": task_id,
        "run_id": run_id,
        "phase": "after_reset_before_agent",
        "evidence_scope": "same_run",
        "started_at": "2026-09-20T20:00:00Z",
        "finished_at": "2026-09-20T20:00:01Z",
        "timeout_seconds": 6.0,
        "dns_attempts": 2,
        "network": {"default_route_present": default_route, "error": None},
        "probes": probes,
    }


def _controller_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "success",
        "output": "guest noise\n"
        + OUTPUT_SENTINEL
        + json.dumps(payload, separators=(",", ":"))
        + "\n",
        "error": "",
        "return_code": 0,
    }


def _parse(
    endpoints: list[PreflightEndpoint], controller_result: dict[str, Any]
) -> dict[str, Any]:
    return parse_controller_result(
        endpoints,
        controller_result,
        task_id=TASK_ID,
        run_id=RUN_ID,
    )


class NetworkPreflightTests(unittest.TestCase):
    def test_environment_hook_fails_closed_without_guest_controller(self) -> None:
        hook = make_environment_preflight(
            task_id=TASK_ID,
            run_id=RUN_ID,
            endpoints=_endpoints(),
        )
        result = hook(object())
        self.assertEqual(result["execution"]["status"], "error")
        self.assertEqual(result["classification"]["status"], "preflight_error")
        self.assertFalse(result["policy"]["assessment_complete"])
        self.assertEqual(validate_preflight_document(result), result)

    def test_high_confidence_dns_only_gate_marks_affected_rubric(self) -> None:
        endpoints = _endpoints()
        probes = [
            _probe(
                endpoint,
                dns=_dns_unresolved(),
                http=_http_failure("gaierror", "Name or service not known"),
            )
            for endpoint in endpoints[:2]
        ] + _healthy_controls(endpoints)

        result = _parse(
            endpoints, _controller_result(_payload(probes))
        )

        self.assertEqual(
            result["classification"]["status"], "target_external_unavailable"
        )
        self.assertEqual(result["classification"]["confidence"], "high")
        self.assertTrue(result["classification"]["infeasible_candidate"])
        self.assertEqual(result["feasibility"]["status"], "infeasible_candidate")
        self.assertEqual(result["feasibility"]["affected_rubric_ids"], ["R1"])
        self.assertEqual(
            result["feasibility"]["affected_target_keys"],
            ["target_apex", "target_www"],
        )
        self.assertFalse(result["classification"]["raw_score_affected"])
        self.assertFalse(result["feasibility"]["raw_score_affected"])
        self.assertEqual(result["classification"]["control_summary"]["healthy"], 2)

    def test_one_resolving_target_alias_cannot_pass_dns_gate(self) -> None:
        endpoints = _endpoints()
        probes = [
            _probe(
                endpoints[0],
                dns=_dns_unresolved(),
                http=_http_failure("gaierror", "Name or service not known"),
            ),
            _probe(
                endpoints[1],
                dns=_dns_resolved("192.0.2.10"),
                http=_http_failure("TimeoutError", "timed out"),
            ),
        ] + _healthy_controls(endpoints)

        result = _parse(
            endpoints, _controller_result(_payload(probes))
        )

        self.assertFalse(result["classification"]["infeasible_candidate"])
        self.assertEqual(result["classification"]["confidence"], "medium")
        self.assertEqual(result["feasibility"]["status"], "indeterminate")
        self.assertEqual(result["feasibility"]["affected_rubric_ids"], [])

    def test_missing_default_route_is_general_network_failure(self) -> None:
        endpoints = _endpoints()
        probes = [
            _probe(
                endpoint,
                dns=_dns_unresolved(),
                http=_http_failure("gaierror", "Name or service not known"),
            )
            for endpoint in endpoints[:2]
        ] + _healthy_controls(endpoints)

        result = _parse(
            endpoints,
            _controller_result(_payload(probes, default_route=False)),
        )

        self.assertEqual(result["classification"]["status"], "general_network_failure")
        self.assertFalse(result["classification"]["infeasible_candidate"])
        self.assertEqual(result["feasibility"]["affected_rubric_ids"], [])

    def test_control_dns_outage_is_not_target_specific(self) -> None:
        endpoints = _endpoints()
        probes = [
            _probe(
                endpoint,
                dns=_dns_unresolved(),
                http=_http_failure("gaierror", "Name or service not known"),
            )
            for endpoint in endpoints
        ]

        result = _parse(
            endpoints, _controller_result(_payload(probes))
        )

        self.assertEqual(result["classification"]["status"], "general_dns_failure")
        self.assertFalse(result["classification"]["infeasible_candidate"])
        self.assertEqual(result["feasibility"]["affected_rubric_ids"], [])

    def test_http_waf_timeout_and_not_found_are_never_dns_eligible(self) -> None:
        endpoints = _endpoints()
        cases = [
            (
                "waf",
                _http_response(403, headers={"CF-Ray": "fixture-SJC"}),
                "target_http_blocked",
                "blocked",
            ),
            (
                "timeout",
                _http_failure("TimeoutError", "The read operation timed out"),
                "target_timeout",
                "timeout",
            ),
            (
                "not-found",
                _http_response(404),
                "indeterminate",
                "not_found",
            ),
        ]
        for name, target_http, overall_status, per_probe_status in cases:
            with self.subTest(name=name):
                probes = [
                    _probe(
                        endpoint,
                        dns=_dns_resolved("192.0.2.44"),
                        http=copy.deepcopy(target_http),
                    )
                    for endpoint in endpoints[:2]
                ] + _healthy_controls(endpoints)
                result = _parse(
                    endpoints, _controller_result(_payload(probes))
                )
                self.assertEqual(
                    result["classification"]["status"], overall_status
                )
                self.assertEqual(result["probes"][0]["http"]["status"], per_probe_status)
                self.assertFalse(result["classification"]["infeasible_candidate"])
                self.assertEqual(result["feasibility"]["affected_rubric_ids"], [])
        waf = _parse(
            endpoints,
            _controller_result(
                _payload(
                    [
                        _probe(
                            endpoint,
                            dns=_dns_resolved("192.0.2.44"),
                            http=_http_response(
                                403, headers={"CF-Ray": "fixture-SJC"}
                            ),
                        )
                        for endpoint in endpoints[:2]
                    ]
                    + _healthy_controls(endpoints)
                )
            ),
        )
        self.assertIn(
            "cloudflare_edge_block", waf["probes"][0]["http"]["block_signals"]
        )

    def test_parser_handles_noise_malformed_payload_and_missing_probe(self) -> None:
        endpoints = _endpoints()
        malformed = {
            "status": "success",
            "output": OUTPUT_SENTINEL + "{not-json}\n",
            "error": "",
            "return_code": 0,
        }
        failed = _parse(endpoints, malformed)
        self.assertEqual(failed["classification"]["status"], "preflight_error")
        self.assertEqual(failed["feasibility"]["status"], "indeterminate")

        probes = [
            _probe(
                endpoint,
                dns=_dns_unresolved(),
                http=_http_failure("gaierror", "not known"),
            )
            for endpoint in endpoints[:2]
        ] + _healthy_controls(endpoints)[:1]
        partial = _parse(
            endpoints, _controller_result(_payload(probes))
        )
        self.assertEqual(partial["classification"]["status"], "preflight_error")
        self.assertFalse(partial["classification"]["infeasible_candidate"])

    def test_guest_script_is_stdlib_only_parallel_and_input_is_not_mutated(self) -> None:
        endpoint_dicts = [endpoint.to_dict() for endpoint in _endpoints()]
        original = copy.deepcopy(endpoint_dicts)
        script = build_guest_probe_script(
            endpoint_dicts,
            task_id=TASK_ID,
            run_id=RUN_ID,
            timeout_seconds=4.0,
            dns_attempts=3,
        )
        compile(script, "<guest-network-preflight>", "exec")
        self.assertEqual(endpoint_dicts, original)
        self.assertIn('multiprocessing.get_context("fork")', script)
        self.assertIn("DNS_JOB_TIMEOUT_SECONDS = 3.0", script)
        self.assertIn("HTTP_JOB_TIMEOUT_SECONDS = 6.0", script)
        self.assertIn("socket.getaddrinfo", script)
        self.assertIn("urllib.request.urlopen", script)
        self.assertIn("class NoRedirect", script)
        self.assertIn("GLOBAL_TIMEOUT_SECONDS = 20.0", script)
        self.assertIn("signal.setitimer", script)
        self.assertIn("HTTP skipped because DNS did not resolve", script)
        self.assertIn("DNS_ATTEMPTS = 3", script)
        self.assertNotIn("subprocess", script)
        self.assertNotIn("ThreadPoolExecutor", script)
        self.assertNotIn("requests", script)
        self.assertNotIn("run_bash_script", script)

    def test_controller_adapter_uses_run_python_and_document_round_trips(self) -> None:
        endpoints = _endpoints()
        probes = [
            _probe(endpoint, dns=_dns_resolved("192.0.2.5"), http=_http_response(200))
            for endpoint in endpoints[:2]
        ] + _healthy_controls(endpoints)

        class Controller:
            def __init__(self) -> None:
                self.scripts: list[str] = []

            def run_python_script(self, script: str) -> dict[str, Any]:
                self.scripts.append(script)
                return _controller_result(_payload(probes))

        controller = Controller()
        result = run_network_preflight(
            controller,
            endpoints,
            task_id=TASK_ID,
            run_id=RUN_ID,
        )
        self.assertEqual(len(controller.scripts), 1)
        self.assertEqual(result["classification"]["status"], "feasible")
        self.assertEqual(result["feasibility"]["status"], "feasible")

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "network_preflight.json"
            write_preflight_document(path, result)
            loaded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(validate_preflight_document(loaded), result)

            changed = copy.deepcopy(loaded)
            changed["feasibility"]["raw_score_affected"] = True
            with self.assertRaises(PreflightResultError):
                write_preflight_document(path, changed)

            forged = copy.deepcopy(loaded)
            forged["classification"]["control_summary"]["healthy"] = 99
            with self.assertRaises(PreflightResultError):
                validate_preflight_document(forged)

    def test_isolated_dns_deadline_preserves_result_and_cannot_mark_infeasible(self) -> None:
        endpoints = _endpoints()
        script = build_guest_probe_script(
            endpoints,
            task_id=TASK_ID,
            run_id=RUN_ID,
            timeout_seconds=1.0,
            dns_attempts=2,
        )
        script = script.replace(
            "DNS_JOB_TIMEOUT_SECONDS = 3.0",
            "DNS_JOB_TIMEOUT_SECONDS = 0.1",
        ).replace(
            "GLOBAL_TIMEOUT_SECONDS = 20.0",
            "GLOBAL_TIMEOUT_SECONDS = 2.0",
        ).replace(
            "records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)",
            "time.sleep(60.0)\n        records = []",
        )
        started = time.monotonic()
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        self.assertLess(time.monotonic() - started, 2.0)
        result = parse_controller_result(
            endpoints,
            {
                "status": "success",
                "output": completed.stdout,
                "error": completed.stderr,
                "return_code": completed.returncode,
            },
            task_id=TASK_ID,
            run_id=RUN_ID,
        )
        self.assertEqual(result["execution"]["status"], "complete")
        self.assertFalse(result["classification"]["infeasible_candidate"])
        self.assertTrue(
            all(
                probe["dns"]["status"] == "resolver_error"
                and not probe["dns"]["all_attempts_unresolved"]
                for probe in result["probes"]
            )
        )

    def test_endpoint_policy_rejects_local_private_and_non_default_ports(self) -> None:
        for url in (
            "http://127.0.0.1/",
            "http://[::1]/",
            "http://10.0.0.1/",
            "http://169.254.169.254/latest/meta-data/",
            "https://service.local/",
            "https://example.com:8443/",
            "https://example.com:80/",
            "http://example.com:443/",
        ):
            with self.subTest(url=url), self.assertRaises(PreflightConfigurationError):
                PreflightEndpoint("unsafe", "target", url)
        public = PreflightEndpoint("public", "target", "https://example.com:443/")
        self.assertEqual(public.host, "example.com")

    def test_sidecar_policy_and_environment_hook_do_not_mutate_task_source(self) -> None:
        policy_path = REPO_ROOT / "personacuabench" / "availability_policies.json"
        tasks_path = REPO_ROOT / "personacuabench" / "tasks.json"
        task_bytes_before = tasks_path.read_bytes()
        task_id = "39255449e341c41a589b8a4e17f073be3a4809c9"
        endpoints = load_task_preflight_endpoints(
            policy_path,
            task_id=task_id,
            rubric_ids=("R1", "R2", "R3", "R4", "R5"),
        )
        self.assertIsNotNone(endpoints)
        assert endpoints is not None
        self.assertEqual(len(endpoints), 7)
        self.assertEqual(
            {item.host for item in endpoints if item.role == "target"},
            {"solecollector.com", "www.solecollector.com"},
        )
        self.assertEqual(
            {
                rubric
                for item in endpoints
                if item.role == "target"
                for rubric in item.affected_rubric_ids
            },
            {"R1"},
        )
        self.assertEqual(tasks_path.read_bytes(), task_bytes_before)
        with self.assertRaises(ConfigurationError):
            load_task_preflight_endpoints(
                policy_path,
                task_id=task_id,
                rubric_ids=("R2", "R3", "R4", "R5"),
            )

        probes = [
            _probe(
                endpoint,
                dns=_dns_unresolved(),
                http=_http_failure("gaierror", "Name or service not known"),
            )
            for endpoint in endpoints
            if endpoint.role == "target"
        ] + [
            _probe(
                endpoint,
                dns=_dns_resolved(f"192.0.2.{index}"),
                http=_http_response(200),
            )
            for index, endpoint in enumerate(
                (item for item in endpoints if item.role == "control"), start=10
            )
        ]

        class Controller:
            def run_python_script(self, _script: str) -> dict[str, Any]:
                return _controller_result(
                    _payload(
                        probes,
                        task_id=task_id,
                        run_id="same-run-hook-fixture",
                    )
                )

        hook = make_environment_preflight(
            task_id=task_id,
            run_id="same-run-hook-fixture",
            endpoints=endpoints,
        )
        result = hook(SimpleNamespace(controller=Controller()))
        self.assertTrue(result["classification"]["assessment_complete"])
        self.assertTrue(result["policy"]["assessment_complete"])
        self.assertEqual(result["policy"]["affected_rubric_ids"], ["R1"])
        self.assertEqual(
            result["policy"]["rubric_mapping_semantics"],
            "exclusive_blocking_dependency",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
