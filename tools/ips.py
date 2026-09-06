#!/usr/bin/env python3
"""Create, apply, and verify classic IPS patches.

The builder uses this tool to produce a distributable patch against the original
Japanese ROM. Patch creation always performs an in-memory round trip, so a bad
patch cannot silently become a release artifact.

usage:
    ips.py create <base.gb> <target.gb> <patch.ips>
    ips.py apply <base.gb> <patch.ips> <output.gb>
    ips.py verify <base.gb> <patch.ips> <target.gb>
    ips.py selftest
"""

import argparse
import hashlib
import os
from pathlib import Path
import tempfile


HEADER = b"PATCH"
EOF_MARKER = b"EOF"
EOF_OFFSET = int.from_bytes(EOF_MARKER, "big")
MAX_OFFSET = 0xFFFFFF
MAX_RECORD_SIZE = 0xFFFF
MIN_RLE_SIZE = 4


class IPSError(ValueError):
    pass


def _be24(value):
    if not 0 <= value <= MAX_OFFSET:
        raise IPSError("value does not fit in an IPS 24-bit field: %d" % value)
    return value.to_bytes(3, "big")


def _source_byte(source, offset):
    return source[offset] if offset < len(source) else 0


def _append_literal(records, offset, data, target):
    """Append literal records while avoiding IPS's reserved EOF offset."""
    position = 0
    while position < len(data):
        record_offset = offset + position
        if record_offset == EOF_OFFSET:
            # A record whose offset spells "EOF" looks like the terminator.
            # Re-write the preceding target byte; overlapping records are legal.
            record_offset -= 1
            chunk = bytes((target[record_offset],)) + data[
                position:position + MAX_RECORD_SIZE - 1
            ]
            position += len(chunk) - 1
        else:
            chunk = data[position:position + MAX_RECORD_SIZE]
            position += len(chunk)
        records.append(_be24(record_offset) + len(chunk).to_bytes(2, "big") + chunk)


def _append_rle(records, offset, length, value, target):
    while length:
        if offset == EOF_OFFSET:
            # Consume the first byte through a literal so the next record starts
            # somewhere other than the reserved offset.
            _append_literal(records, offset - 1, bytes((target[offset - 1], value)), target)
            offset += 1
            length -= 1
            continue
        chunk = min(length, MAX_RECORD_SIZE)
        records.append(
            _be24(offset)
            + b"\x00\x00"
            + chunk.to_bytes(2, "big")
            + bytes((value,))
        )
        offset += chunk
        length -= chunk


def create_patch(source, target):
    if len(target) > MAX_OFFSET:
        raise IPSError("classic IPS cannot represent a target larger than 0xFFFFFF bytes")

    records = []
    literal_count = 0
    rle_count = 0
    offset = 0

    while offset < len(target):
        if target[offset] == _source_byte(source, offset):
            offset += 1
            continue

        span_start = offset
        while offset < len(target) and target[offset] != _source_byte(source, offset):
            offset += 1
        span = target[span_start:offset]

        position = 0
        literal_start = 0
        while position < len(span):
            run_end = position + 1
            while run_end < len(span) and span[run_end] == span[position]:
                run_end += 1
            run_length = run_end - position
            if run_length >= MIN_RLE_SIZE:
                if literal_start < position:
                    before = len(records)
                    _append_literal(
                        records,
                        span_start + literal_start,
                        span[literal_start:position],
                        target,
                    )
                    literal_count += len(records) - before
                before = len(records)
                _append_rle(
                    records,
                    span_start + position,
                    run_length,
                    span[position],
                    target,
                )
                rle_count += len(records) - before
                position = run_end
                literal_start = position
            else:
                position = run_end

        if literal_start < len(span):
            before = len(records)
            _append_literal(records, span_start + literal_start, span[literal_start:], target)
            literal_count += len(records) - before

    # The optional size after EOF is the standard IPS truncate/expand extension.
    # It guarantees a 512 KiB base becomes exactly the 1 MiB target.
    patch = HEADER + b"".join(records) + EOF_MARKER + _be24(len(target))
    rebuilt = apply_patch(source, patch)
    if rebuilt != target:
        raise IPSError("internal IPS round-trip verification failed")
    return patch, literal_count, rle_count


def apply_patch(source, patch):
    if not patch.startswith(HEADER):
        raise IPSError("missing IPS PATCH header")

    output = bytearray(source)
    position = len(HEADER)
    while True:
        if position + 3 > len(patch):
            raise IPSError("patch ended before EOF marker")
        offset_bytes = patch[position:position + 3]
        position += 3
        if offset_bytes == EOF_MARKER:
            break
        offset = int.from_bytes(offset_bytes, "big")

        if position + 2 > len(patch):
            raise IPSError("truncated IPS record size")
        size = int.from_bytes(patch[position:position + 2], "big")
        position += 2
        if size:
            if position + size > len(patch):
                raise IPSError("truncated IPS literal record")
            data = patch[position:position + size]
            position += size
        else:
            if position + 3 > len(patch):
                raise IPSError("truncated IPS RLE record")
            run_length = int.from_bytes(patch[position:position + 2], "big")
            value = patch[position + 2]
            position += 3
            if run_length == 0:
                raise IPSError("IPS RLE record has zero length")
            data = bytes((value,)) * run_length

        end = offset + len(data)
        if end > len(output):
            output.extend(b"\x00" * (end - len(output)))
        output[offset:end] = data

    remaining = len(patch) - position
    if remaining == 3:
        final_size = int.from_bytes(patch[position:position + 3], "big")
        if final_size < len(output):
            del output[final_size:]
        elif final_size > len(output):
            output.extend(b"\x00" * (final_size - len(output)))
    elif remaining != 0:
        raise IPSError("IPS patch has %d unexpected trailing bytes" % remaining)
    return bytes(output)


def _read(path):
    return Path(path).read_bytes()


def _write_atomic(path, data):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        temporary.chmod(0o644)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def command_create(args):
    source = _read(args.source)
    target = _read(args.target)
    patch, literals, rles = create_patch(source, target)
    _write_atomic(args.patch, patch)
    print(
        "ips: wrote %s (%d bytes; %d literal, %d RLE records)"
        % (args.patch, len(patch), literals, rles)
    )
    print("ips: verified base + patch -> target (sha256 %s)" % _sha256(target))


def command_apply(args):
    output = apply_patch(_read(args.source), _read(args.patch))
    _write_atomic(args.output, output)
    print("ips: wrote %s (%d bytes; sha256 %s)" % (args.output, len(output), _sha256(output)))


def command_verify(args):
    target = _read(args.target)
    output = apply_patch(_read(args.source), _read(args.patch))
    if output != target:
        raise IPSError(
            "patch result does not match target (got %s, expected %s)"
            % (_sha256(output), _sha256(target))
        )
    print("ips: verified %s -> %s (sha256 %s)" % (args.patch, args.target, _sha256(target)))


def command_selftest(_args):
    cases = [
        (b"abcdef", b"abZdef", "literal"),
        (b"abc", b"abc" + b"\xFF" * 200000, "RLE expansion"),
        (b"abcdefgh", b"abc", "truncation"),
    ]
    # Exercise the otherwise rare reserved-offset escape explicitly.
    source = b"\x00" * (EOF_OFFSET + 2)
    target = bytearray(source)
    target[EOF_OFFSET] = 0x7A
    cases.append((source, bytes(target), "reserved EOF offset"))

    for source, target, label in cases:
        patch, _literals, _rles = create_patch(source, target)
        if apply_patch(source, patch) != target:
            raise IPSError("self-test failed: %s" % label)
    print("ips: all %d self-tests passed" % len(cases))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="create and round-trip verify an IPS patch")
    create.add_argument("source")
    create.add_argument("target")
    create.add_argument("patch")
    create.set_defaults(function=command_create)

    apply = subparsers.add_parser("apply", help="apply an IPS patch")
    apply.add_argument("source")
    apply.add_argument("patch")
    apply.add_argument("output")
    apply.set_defaults(function=command_apply)

    verify = subparsers.add_parser("verify", help="verify a patch against an expected target")
    verify.add_argument("source")
    verify.add_argument("patch")
    verify.add_argument("target")
    verify.set_defaults(function=command_verify)

    selftest = subparsers.add_parser("selftest", help="run IPS codec self-tests")
    selftest.set_defaults(function=command_selftest)

    args = parser.parse_args()
    try:
        args.function(args)
    except (IPSError, OSError) as error:
        parser.exit(1, "ips: ERROR: %s\n" % error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
