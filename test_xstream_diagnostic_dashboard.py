import http.client
import json
import socket
import threading
import unittest
from unittest.mock import patch

from xstream_diagnostic_dashboard import (
    DashboardServer,
    ValidationError,
    check_port,
    markdown_export,
    normalize_ports,
    normalize_timeout,
    parse_dial_description,
    probe_dial,
    run_scan,
    validate_target,
)


class ValidationTests(unittest.TestCase):
    def test_private_ipv4_targets_are_accepted(self) -> None:
        for target in ("192.168.1.10", "10.0.0.8", "172.16.4.4", "127.0.0.1", "169.254.10.20"):
            with self.subTest(target=target):
                self.assertEqual(validate_target(target), target)

    def test_public_and_named_targets_are_rejected(self) -> None:
        for target in ("8.8.8.8", "example.com", "2001:4860:4860::8888", ""):
            with self.subTest(target=target):
                with self.assertRaises(ValidationError):
                    validate_target(target)

    def test_only_fixed_ports_are_accepted(self) -> None:
        self.assertEqual(normalize_ports([8443, 22, 8443, 8008]), (22, 8008, 8443))
        with self.assertRaises(ValidationError):
            normalize_ports([80, 81])
        with self.assertRaises(ValidationError):
            normalize_ports([])

    def test_timeout_is_bounded(self) -> None:
        self.assertEqual(normalize_timeout("1.25"), 1.25)
        for timeout in (0.1, 5.1, "invalid", True):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValidationError):
                    normalize_timeout(timeout)


class ProbeTests(unittest.TestCase):
    def test_dial_description_parser(self) -> None:
        payload = b"""<?xml version="1.0"?>
        <root xmlns="urn:schemas-upnp-org:device-1-0">
          <device>
            <friendlyName>Living Room</friendlyName>
            <manufacturer>Technicolor</manufacturer>
            <modelName>XStream_Smart_Box_001</modelName>
          </device>
        </root>"""
        self.assertEqual(
            parse_dial_description(payload),
            {
                "friendlyName": "Living Room",
                "manufacturer": "Technicolor",
                "modelName": "XStream_Smart_Box_001",
            },
        )

    @patch("xstream_diagnostic_dashboard.http_get")
    def test_dial_probe_uses_documented_path(self, http_get) -> None:
        http_get.return_value = (
            200,
            b"""<root xmlns=\"urn:schemas-upnp-org:device-1-0\"><device><friendlyName>Test</friendlyName><manufacturer>Test</manufacturer><modelName>Test</modelName></device></root>""",
            None,
        )
        result = probe_dial("192.168.1.10", 1.0)
        self.assertEqual(result["state"], "ok")
        self.assertEqual(
            http_get.call_args.args[0],
            "http://192.168.1.10:8008/ssdp/device-desc.xml",
        )

    def test_open_local_port(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        accepted = threading.Event()

        def accept_once() -> None:
            connection, _ = listener.accept()
            connection.close()
            accepted.set()

        thread = threading.Thread(target=accept_once)
        thread.start()
        result = check_port("127.0.0.1", port, 0.5)
        thread.join(timeout=1)
        listener.close()
        self.assertTrue(accepted.is_set())
        self.assertEqual(result["state"], "open")

    def test_run_scan_reports_read_only_scope(self) -> None:
        result = run_scan("127.0.0.1", (22,), 0.2, include_service_probes=False)
        self.assertTrue(result["read_only"])
        self.assertEqual(result["target"], "127.0.0.1")
        self.assertEqual(result["summary"]["selected"], 1)
        self.assertEqual(result["dial"]["state"], "skipped")
        self.assertIn("No reset", " ".join(result["excluded"]))

    def test_markdown_export(self) -> None:
        result = run_scan("127.0.0.1", (53,), 0.2, include_service_probes=False)
        markdown = markdown_export(result)
        self.assertIn("# XStream Read-only Diagnostic", markdown)
        self.assertIn("`127.0.0.1`", markdown)
        self.assertIn("## Safety scope", markdown)


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = DashboardServer(("127.0.0.1", 0), "test-token", "test-nonce", "192.168.1.10")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def request(self, method: str, path: str, body: dict[str, object] | None = None, token: str | None = None) -> tuple[int, dict[str, object]]:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        headers = {"Host": f"127.0.0.1:{self.server.server_port}"}
        payload = None
        if body is not None:
            payload = json.dumps(body)
            headers["Content-Type"] = "application/json"
        if token is not None:
            headers["X-CSRF-Token"] = token
        connection.request(method, path, body=payload, headers=headers)
        response = connection.getresponse()
        data = json.loads(response.read())
        connection.close()
        return response.status, data

    def test_health_and_security_gates(self) -> None:
        status, health = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "ok")
        status, response = self.request(
            "POST",
            "/api/scan",
            {"target": "192.168.1.10", "timeout": 0.2, "ports": [22], "confirm_authorization": True},
        )
        self.assertEqual(status, 403)
        self.assertIn("token", response["error"])
        status, response = self.request(
            "POST",
            "/api/scan",
            {"target": "8.8.8.8", "timeout": 0.2, "ports": [22], "confirm_authorization": True},
            "test-token",
        )
        self.assertEqual(status, 400)
        self.assertIn("private", response["error"])


if __name__ == "__main__":
    unittest.main()
