#!/usr/bin/env python3
"""Encode the AcoustID API key for embedding in acoustid.py.

Usage:
    python scripts/encode_acoustid_key.py <plaintext_key>

Prints a Python bytes literal (e.g. b"\\x0e\\x07...") that replaces the
_KEY placeholder in kamp_daemon/acoustid.py.  The CI release workflow
pipes this output into sed to patch the source before building.

XOR salt matches the decoder in acoustid._api_key(): b"kamp".
"""

import sys


def encode(key: str) -> str:
    salt = b"kamp"
    encoded = bytes(ord(c) ^ salt[i % len(salt)] for i, c in enumerate(key))
    # Produce a Python bytes literal with hex escapes for every byte.
    inner = "".join(f"\\x{b:02x}" for b in encoded)
    return f'b"{inner}"'


if __name__ == "__main__":
    if len(sys.argv) != 2 or not sys.argv[1]:
        print("Usage: encode_acoustid_key.py <key>", file=sys.stderr)
        sys.exit(1)
    print(encode(sys.argv[1]))
