"""Offline contract tests. The fixture is metadata-only, never market data."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay_verified import CaptureRejected, ReplayWitness, inspect_capture, verify


class CaptureMetadataContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pcap = Path(self.temp.name) / "capture.pcap.zst"
        self.pcap.write_bytes(b"not real market data: metadata tests only" * 4)
        self.meta = self.pcap.with_name("capture.meta.json")
        self.m = {
            "version": 1, "cryptofeed_version": "3.0.5",
            "files": [self.pcap.name],
            "feeds": [{"exchange": "KRAKEN", "symbols": ["BTC-USD"],
                       "channels": ["trades", "l2_book"]}],
            "streams": [{"exchange": "KRAKEN", "kind": "ws", "messages": 11}]
        }
        self.write()

    def write(self):
        self.meta.write_text(json.dumps(self.m), encoding="utf-8")

    def inspect(self):
        return inspect_capture(self.pcap, "KRAKEN", "BTC-USD")

    def test_valid_manifest_identity_only(self):
        result = self.inspect()
        self.assertEqual(result["recorded_ws_messages"], 11)
        self.assertEqual(len(result["pcap_sha256"]), 64)
        self.assertNotIn("VERIFIED_REAL_CAPTURE_REPLAY", result.values())

    def test_missing_capture_rejected(self):
        self.pcap.unlink()
        with self.assertRaises(CaptureRejected): self.inspect()

    def test_missing_metadata_rejected(self):
        self.meta.unlink()
        with self.assertRaises(CaptureRejected): self.inspect()

    def test_wrong_venue_rejected(self):
        self.m["feeds"][0]["exchange"] = "BINANCE"
        self.write()
        with self.assertRaises(CaptureRejected): self.inspect()

    def test_wrong_symbol_rejected(self):
        self.m["feeds"][0]["symbols"] = ["ETH-USD"]
        self.write()
        with self.assertRaises(CaptureRejected): self.inspect()

    def test_missing_trades_channel_rejected(self):
        self.m["feeds"][0]["channels"] = ["l2_book"]
        self.write()
        with self.assertRaises(CaptureRejected): self.inspect()

    def test_missing_depth_channel_rejected(self):
        self.m["feeds"][0]["channels"] = ["trades"]
        self.write()
        with self.assertRaises(CaptureRejected): self.inspect()

    def test_foreign_stream_rejected(self):
        self.m["streams"].append({"exchange": "BINANCE", "kind": "ws", "messages": 100})
        self.write()
        with self.assertRaises(CaptureRejected): self.inspect()

    def test_zero_websocket_frames_rejected(self):
        self.m["streams"][0]["messages"] = 0
        self.write()
        with self.assertRaises(CaptureRejected): self.inspect()

    def test_rotated_files_rejected(self):
        self.m["files"] = [self.pcap.name, "capture.1.pcap.zst"]
        self.write()
        with self.assertRaises(CaptureRejected): self.inspect()

    def test_producer_version_rejected(self):
        self.m["cryptofeed_version"] = "0.0.0"
        self.write()
        with self.assertRaises(CaptureRejected): self.inspect()

    def test_wrong_pcap_attestation_rejected(self):
        with self.assertRaisesRegex(CaptureRejected, "PCAP_HASH_ATTESTATION_MISMATCH"):
            inspect_capture(self.pcap, "KRAKEN", "BTC-USD", expected_pcap_sha256="a" * 64)

    def test_wrong_metadata_attestation_rejected(self):
        with self.assertRaisesRegex(CaptureRejected, "METADATA_HASH_ATTESTATION_MISMATCH"):
            inspect_capture(self.pcap, "KRAKEN", "BTC-USD", expected_meta_sha256="b" * 64)

    def test_truncated_replay_count_rejected_even_if_decoder_did_not_raise(self):
        incomplete = {"trades": 1, "books": 1, "messages_processed": 9,
                      "http_requests_served": 1, "order_regressions": 0,
                      "last_bid": "10", "last_ask": "11"}
        with patch("replay_verified.replay_once", return_value=incomplete):
            with self.assertRaisesRegex(CaptureRejected, "RECORDED_MESSAGE_COUNT_MISMATCH"):
                verify(self.pcap, "KRAKEN", "BTC-USD", repeat=2)

    def test_fake_non_pcap_payload_never_verifies(self):
        # Metadata that looks correct cannot turn fake bytes into verified events.
        with patch("replay_verified.replay_once", side_effect=ValueError("bad PCAP")):
            with self.assertRaises(ValueError):
                verify(self.pcap, "KRAKEN", "BTC-USD")


class ReplayRuntimeContract(unittest.TestCase):
    def test_no_events_fail_closed(self):
        w = ReplayWitness("KRAKEN", "BTC-USD")
        result = NS(callbacks={}, order_regressions=0, messages_processed=10)
        with self.assertRaises(CaptureRejected): w.checks(result)

    def test_order_regression_rejected(self):
        w = ReplayWitness("KRAKEN", "BTC-USD", trades=1, books=1)
        result = NS(callbacks={"trades": 1, "l2_book": 1}, order_regressions=1, messages_processed=2)
        with self.assertRaises(CaptureRejected): w.checks(result)

    def test_mismatched_callback_count_rejected(self):
        w = ReplayWitness("KRAKEN", "BTC-USD", trades=1, books=1)
        result = NS(callbacks={"trades": 2, "l2_book": 1}, order_regressions=0, messages_processed=3)
        with self.assertRaises(CaptureRejected): w.checks(result)


if __name__ == "__main__":
    unittest.main()
