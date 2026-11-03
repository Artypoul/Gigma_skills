#!/usr/bin/env python3
"""Compare forward TCP byte ranges in two bounded IPv4 tcpdump -nn -S texts.

No network access. An observed gap is evidence in files, not a root-cause verdict.
"""

import argparse
import ipaddress
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Flow:
    syn: set = field(default_factory=set)
    ranges: list = field(default_factory=list)
    acks: list = field(default_factory=list)
    sacks: list = field(default_factory=list)
    issues: list = field(default_factory=list)


def merge(ranges):
    result = []
    for lo, hi in sorted(ranges):
        if not result or lo > result[-1][1]:
            result.append([lo, hi])
        else:
            result[-1][1] = max(hi, result[-1][1])
    return result


def subtract(left, right):
    """Return disjoint intervals in union(left) minus union(right)."""
    result = []
    right = merge(right)
    for lo, hi in merge(left):
        cursor = lo
        for other_lo, other_hi in right:
            if other_hi <= cursor:
                continue
            if other_lo >= hi:
                break
            if other_lo > cursor:
                result.append([cursor, min(other_lo, hi)])
            cursor = max(cursor, other_hi)
            if cursor >= hi:
                break
        if cursor < hi:
            result.append([cursor, hi])
    return result


def byte_count(ranges):
    return sum(hi - lo for lo, hi in ranges)


def parse(text, source, target, port):
    src, dst = re.escape(source), re.escape(target)
    forward = re.compile(rf"{src}\.(\d+) > {dst}\.{port}: Flags \[([^]]+)\](.*)")
    reverse = re.compile(rf"{dst}\.{port} > {src}\.(\d+): Flags \[([^]]+)\](.*)")
    flows = {}
    warnings = []
    drops = [int(x) for x in re.findall(r"(?m)^\s*(\d+) packets dropped by kernel\s*$", text)]
    if len(drops) != 1:
        warnings.append("need_exactly_one_final_drop_counter")
    elif drops[0] != 0:
        warnings.append("capture_kernel_drops")
    interface_drops = [int(x) for x in re.findall(r"(?m)^\s*(\d+) packets dropped by interface\s*$", text)]
    if any(interface_drops):
        warnings.append("capture_interface_drops")
    if "[|tcp]" in text or "[|ip]" in text:
        warnings.append("truncated_headers")

    for line in text.splitlines():
        tx = forward.search(line)
        rx = None if tx else reverse.search(line)
        match = tx or rx
        if not match:
            continue
        source_port, flags, tail = match.groups()
        flow = flows.setdefault(int(source_port), Flow())
        if rx:
            ack = re.search(r"\back (\d+)\b", tail)
            if ack:
                flow.acks.append(int(ack[1]))
            if re.search(r"\bsack\b", tail):
                sack = re.search(r"\bsack\s+(\d+)\s+((?:\{\d+:\d+\}\s*)+)", tail)
                blocks = re.findall(r"\{(\d+):(\d+)\}", sack[2]) if sack else []
                if not sack or not 1 <= int(sack[1]) <= 4 or len(blocks) != int(sack[1]) or not ack:
                    flow.issues.append("malformed_receiver_sack")
                for lo, hi in blocks:
                    lo, hi = int(lo), int(hi)
                    if not 0 <= lo < hi < 2**32:
                        flow.issues.append("invalid_or_wrapped_sack_range")
                    else:
                        flow.sacks.append((lo, hi))
            continue
        if "S" in flags:
            initial = re.search(r"\bseq (\d+)\b", tail)
            if initial and flags == "S":
                flow.syn.add(int(initial[1]))
            else:
                flow.issues.append("unsupported_syn_record")
        length = re.search(r"\blength (\d+)\s*$", tail)
        if not length:
            flow.issues.append("missing_payload_length")
            continue
        if int(length[1]) == 0:
            continue
        seq = re.search(r"\bseq (\d+):(\d+)\b", tail)
        if not seq:
            flow.issues.append("missing_payload_seq_range")
            continue
        lo, hi = map(int, seq.groups())
        if "S" in flags:
            flow.issues.append("payload_with_syn_unsupported")
        if not 0 <= lo < hi < 2**32 or hi - lo != int(length[1]):
            flow.issues.append("invalid_or_wrapped_seq_range")
            continue
        flow.ranges.append((lo, hi))
    return flows, drops[0] if len(drops) == 1 else None, warnings


def compare(sender_text, receiver_text, source, target, port, source_ports=None):
    sender, sender_drops, sender_warnings = parse(sender_text, source, target, port)
    receiver, receiver_drops, receiver_warnings = parse(receiver_text, source, target, port)
    warnings = ["sender:" + x for x in sender_warnings]
    warnings += ["receiver:" + x for x in receiver_warnings]
    output = {
        "source": source, "target": target, "target_port": port,
        "selected_source_ports": sorted(source_ports) if source_ports else None,
        "sender_capture_drops": sender_drops, "receiver_capture_drops": receiver_drops,
        "warnings": warnings, "flows": [],
        "interpretation": "File observations only. Verify absolute seq, aligned capture windows, interfaces and actual client outcome before attributing network loss.",
    }
    selected = set(source_ports or [])
    for source_port in sorted(set(sender) | set(receiver) | selected):
        if source_ports and source_port not in source_ports:
            continue
        tx, rx = sender.get(source_port, Flow()), receiver.get(source_port, Flow())
        has_activity = bool(tx.syn or rx.syn or tx.ranges or rx.ranges)
        if not has_activity and source_port not in selected:
            continue  # Ignore ACK/FIN-only records of pre-existing connections.
        issues = list(warnings) + tx.issues + rx.issues
        if not has_activity:
            issues.append("selected_flow_not_found")
        if len(tx.syn) != 1 or len(rx.syn) != 1 or tx.syn != rx.syn:
            issues.append("missing_or_ambiguous_matching_syn")
        start = next(iter(tx.syn)) + 1 if len(tx.syn) == 1 else None
        tx_union, rx_union = merge(tx.ranges), merge(rx.ranges)
        missing, extra = subtract(tx_union, rx_union), subtract(rx_union, tx_union)
        if not tx_union:
            issues.append("no_sender_payload")
        all_ranges = tx_union + rx_union
        if start is not None and any(lo < start or hi - start >= 2**31 for lo, hi in all_ranges):
            issues.append("relative_seq_wrap_or_large_span_unsupported")
        if extra:
            issues.append("receiver_has_bytes_absent_from_sender_capture")
        ack = max(rx.acks) if rx.acks else None
        if missing and ack is None:
            issues.append("missing_receiver_ack")
        # ACK/SACK from the data receiver can be visible at either capture point.
        # A received acknowledgement must not be ignored just because the
        # receiver-side text did not contain its outgoing packet.
        for vantage, flow in (("sender", tx), ("receiver", rx)):
            if start is not None:
                if any(value < start or value >= 2**32 or value - start >= 2**31 for value in flow.acks):
                    issues.append(f"invalid_or_wrapped_{vantage}_ack")
                if any(lo < start or hi - start >= 2**31 for lo, hi in flow.sacks):
                    issues.append(f"relative_or_wrapped_{vantage}_sack")
            if any(value > lo for lo, hi in missing for value in flow.acks):
                issues.append(f"{vantage}_ack_contradicts_observed_gap")
            if any(max(lo, sack_lo) < min(hi, sack_hi) for lo, hi in missing for sack_lo, sack_hi in flow.sacks):
                issues.append(f"{vantage}_sack_contradicts_observed_gap")
        issues = sorted(set(issues))
        status = "inconclusive" if issues else ("observed_gap" if missing else "same_observed_bytes")
        relative = lambda ranges: [[lo - start, hi - start] for lo, hi in ranges] if start is not None else None
        output["flows"].append({
            "source_port": source_port, "status": status, "issues": issues,
            "sender_unique_payload_bytes": byte_count(tx_union),
            "receiver_unique_payload_bytes": byte_count(rx_union),
            "missing_unique_bytes": byte_count(missing), "extra_unique_bytes": byte_count(extra),
            "sender_payload_records": len(tx.ranges), "receiver_payload_records": len(rx.ranges),
            "sender_ranges_relative": relative(tx_union), "receiver_ranges_relative": relative(rx_union),
            "missing_ranges_relative": relative(missing), "extra_ranges_relative": relative(extra),
            "receiver_max_ack_relative": ack - start if ack is not None and start is not None else None,
            "receiver_sack_ranges_relative": relative(merge(rx.sacks)),
            "sender_observed_max_ack_relative": max(tx.acks) - start if tx.acks and start is not None else None,
            "sender_observed_sack_ranges_relative": relative(merge(tx.sacks)),
        })
    if not output["flows"]:
        output["warnings"].append("no_matching_new_flows_or_payload")
    output["status"] = (
        "inconclusive" if output["warnings"] or not output["flows"] or any(f["status"] == "inconclusive" for f in output["flows"])
        else "observed_gap" if any(f["status"] == "observed_gap" for f in output["flows"])
        else "same_observed_bytes"
    )
    return output


def ipv4(value):
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError as error:
        raise argparse.ArgumentTypeError("An IPv4 address is required") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sender", type=Path)
    parser.add_argument("receiver", type=Path)
    parser.add_argument("--source", required=True, type=ipv4)
    parser.add_argument("--target", required=True, type=ipv4)
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--source-port", type=int, action="append", help="Analyze only this initiating port; repeat for multiple known test flows")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.source_port and any(not 1 <= value <= 65535 for value in args.source_port):
        parser.error("--source-port must be between 1 and 65535")
    if args.source == args.target:
        parser.error("--source and --target must differ")
    try:
        inputs = (args.sender, args.receiver)
        if args.output and (
            args.output.resolve() in {path.resolve() for path in inputs}
            or (args.output.exists() and any(args.output.samefile(path) for path in inputs))
        ):
            parser.error("--output must not overwrite a capture, including a hard link")
        result = compare(args.sender.read_text(encoding="utf-8-sig"), args.receiver.read_text(encoding="utf-8-sig"), args.source, args.target, args.port, set(args.source_port or []))
        encoded = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
        if args.output:
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
    except (OSError, UnicodeError) as error:
        parser.exit(2, f"Capture I/O error: {error}\n")


if __name__ == "__main__":
    main()
