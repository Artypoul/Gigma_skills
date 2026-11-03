"""Offline acceptance checks for the reusable TCP evidence comparator."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT.parent / "skills/vps-node-network-setup/scripts/compare_tcp_sequences.py"
spec = importlib.util.spec_from_file_location("tcp_comparison", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
SRC, DST = "192.0.2.10", "198.51.100.20"
SYN = f"1.0 IP {SRC}.50000 > {DST}.443: Flags [S], seq 100, win 1000, length 0\n"
END = "4 packets captured\n4 packets received by filter\n0 packets dropped by kernel\n"


def payload(lo, hi):
    return f"1.1 IP {SRC}.50000 > {DST}.443: Flags [P.], seq {lo}:{hi}, ack 2, win 1000, length {hi-lo}\n"


def ack(seq):
    return f"1.2 IP {DST}.443 > {SRC}.50000: Flags [.], ack {seq}, win 1000, length 0\n"


def compare(sender, receiver):
    return module.compare(sender, receiver, SRC, DST, 443)


class TcpEvidenceTests(unittest.TestCase):
    def test_segmentation_overlap_reordering_and_retransmission(self):
        a = SYN + payload(101, 301) + payload(151, 301) + END
        b = SYN + payload(201, 301) + payload(101, 251) + ack(301) + END
        r = compare(a, b)
        self.assertEqual(r["status"], "same_observed_bytes")
        self.assertEqual(r["flows"][0]["sender_unique_payload_bytes"], 200)

    def test_missing_tail_is_gap_with_bounded_ack(self):
        a = SYN + payload(101, 301) + payload(251, 301) * 3 + END
        b = SYN + payload(101, 251) + ack(251) + END
        r = compare(a, b)
        self.assertEqual(r["status"], "observed_gap")
        self.assertEqual(r["flows"][0]["missing_ranges_relative"], [[150, 200]])

    def test_fin_can_retransmit_payload_without_changing_unique_byte_count(self):
        a = SYN + payload(101, 301) + payload(251, 301).replace("[P.]", "[FP.]") + END
        b = SYN + payload(101, 251) + ack(251) + END
        r = compare(a, b)
        self.assertEqual(r["status"], "observed_gap")
        self.assertEqual(r["flows"][0]["missing_unique_bytes"], 50)

    def test_same_byte_count_different_ranges_is_inconclusive(self):
        r = compare(SYN + payload(101, 201) + END, SYN + payload(201, 301) + ack(301) + END)
        self.assertEqual(r["status"], "inconclusive")
        self.assertEqual(r["flows"][0]["missing_unique_bytes"], 100)
        self.assertEqual(r["flows"][0]["extra_unique_bytes"], 100)

    def test_drops_unknown_or_nonzero(self):
        for ending in ("", END.replace("0 packets dropped", "2 packets dropped"), END + END):
            r = compare(SYN + payload(101, 301) + END, SYN + payload(101, 201) + ack(201) + ending)
            self.assertEqual(r["status"], "inconclusive")

    def test_missing_syn_and_reused_port(self):
        for syn in ("", SYN.replace("seq 100,", "seq 200,") + SYN):
            r = compare(SYN + payload(101, 301) + END, syn + payload(101, 201) + ack(201) + END)
            self.assertEqual(r["status"], "inconclusive")

    def test_ack_proves_gap_is_capture_artifact_or_window_problem(self):
        r = compare(SYN + payload(101, 301) + END, SYN + payload(101, 201) + ack(301) + END)
        self.assertEqual(r["status"], "inconclusive")
        self.assertIn("receiver_ack_contradicts_observed_gap", r["flows"][0]["issues"])

    def test_wrapped_or_relative_sequences_are_rejected(self):
        for data in (payload(1, 101), payload(4294967290, 4294967300)):
            r = compare(SYN + data + END, SYN + data + END)
            self.assertEqual(r["status"], "inconclusive")

    def test_capture_without_matching_payload_is_inconclusive(self):
        self.assertEqual(compare(END, END)["status"], "inconclusive")

    def test_truncated_headers_are_inconclusive(self):
        r = compare(SYN + payload(101, 301) + END, SYN + payload(101, 301) + "[|tcp]\n" + END)
        self.assertEqual(r["status"], "inconclusive")

    def test_requested_port_without_capture_is_reported(self):
        capture = SYN + payload(101, 301) + ack(301) + END
        r = module.compare(capture, capture, SRC, DST, 443, {50000, 50001})
        self.assertEqual(r["status"], "inconclusive")
        absent = next(f for f in r["flows"] if f["source_port"] == 50001)
        self.assertIn("selected_flow_not_found", absent["issues"])

    def test_receiver_ack_below_syn_is_not_valid_evidence(self):
        r = compare(SYN + payload(101, 301) + END, SYN + payload(101, 201) + ack(1) + END)
        self.assertEqual(r["status"], "inconclusive")

    def test_receiver_sack_contradicts_missing_tail(self):
        for blocks in ("1 {251:301}", "2 {251:271}{281:301}"):
            reply = ack(201).replace("win 1000,", f"win 1000, options [nop,nop,sack {blocks}],")
            r = compare(SYN + payload(101, 301) + END, SYN + payload(101, 201) + reply + END)
            self.assertEqual(r["status"], "inconclusive")
            flow = r["flows"][0]
            self.assertIn("receiver_sack_contradicts_observed_gap", flow["issues"])
            self.assertEqual(flow["missing_unique_bytes"], 100)

    def test_ack_seen_only_at_sender_also_contradicts_gap(self):
        a = SYN + payload(101, 301) + ack(301) + END
        b = SYN + payload(101, 201) + ack(201) + END
        r = compare(a, b)
        self.assertEqual(r["status"], "inconclusive")
        self.assertIn("sender_ack_contradicts_observed_gap", r["flows"][0]["issues"])

    def test_sack_seen_only_at_sender_also_contradicts_gap(self):
        reply = ack(201).replace("win 1000,", "win 1000, options [sack 1 {251:301}],")
        a = SYN + payload(101, 301) + reply + END
        b = SYN + payload(101, 201) + ack(201) + END
        r = compare(a, b)
        self.assertEqual(r["status"], "inconclusive")
        self.assertIn("sender_sack_contradicts_observed_gap", r["flows"][0]["issues"])

    def test_sack_for_captured_bytes_does_not_hide_real_hole(self):
        reply = ack(201).replace("win 1000,", "win 1000, options [sack 1 {251:301}],")
        a = SYN + payload(101, 301) + END
        b = SYN + payload(101, 201) + payload(251, 301) + reply + END
        r = compare(a, b)
        self.assertEqual(r["status"], "observed_gap")
        self.assertEqual(r["flows"][0]["missing_unique_bytes"], 50)

    def test_interface_capture_drops_make_comparison_inconclusive(self):
        a = SYN + payload(101, 301) + END
        b = SYN + payload(101, 201) + ack(201) + END + "2 packets dropped by interface\n"
        self.assertEqual(compare(a, b)["status"], "inconclusive")

    def test_malformed_sack_is_inconclusive(self):
        reply = ack(201).replace("win 1000,", "win 1000, options [sack 2 {251:301}],")
        r = compare(SYN + payload(101, 301) + END, SYN + payload(101, 201) + reply + END)
        self.assertEqual(r["status"], "inconclusive")

    def test_hardlinked_output_cannot_overwrite_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b, output = [Path(directory) / name for name in ("sender.txt", "receiver.txt", "output.json")]
            original = SYN + payload(101, 301) + END
            a.write_text(original, encoding="utf-8")
            b.write_text(original, encoding="utf-8")
            try:
                os.link(a, output)
            except OSError as error:
                self.skipTest("Hard links unavailable: " + str(error))
            before = a.read_bytes()
            result = subprocess.run([sys.executable, str(SCRIPT), str(a), str(b), "--source", SRC, "--target", DST, "--output", str(output)], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(a.read_bytes(), before)

    def test_cli_selected_flows(self):
        with tempfile.TemporaryDirectory() as directory:
            a, b = [Path(directory) / name for name in ("sender.txt", "receiver.txt")]
            a.write_text(SYN + payload(101, 301) + END, encoding="utf-8")
            b.write_text(SYN + payload(101, 201) + ack(201) + END, encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(a), str(b), "--source", SRC, "--target", DST, "--source-port", "50000", "--source-port", "50001"], check=True, capture_output=True, text=True)
            evidence = json.loads(result.stdout)
            by_port = {f["source_port"]: f for f in evidence["flows"]}
            self.assertEqual(by_port[50000]["status"], "observed_gap")
            self.assertEqual(by_port[50000]["missing_unique_bytes"], 100)
            self.assertEqual(by_port[50001]["status"], "inconclusive")
            self.assertEqual(evidence["status"], "inconclusive")


if __name__ == "__main__":
    unittest.main(verbosity=2)
