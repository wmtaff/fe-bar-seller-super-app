"""Stable, Salesforce-shaped identifiers derived from (seed, object, index).

An 18-char Salesforce Id = 15-char case-sensitive Id + 3-char case-safe
checksum suffix. Ours: key prefix (3) + seed "pod" (2) + "0" + base62 index (9).
"""

import hashlib

_B62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_SUFFIX = "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"

KEY_PREFIX = {
    "User": "005",
    "UserRole": "00E",
    "Account": "001",
    "Contact": "003",
    "Opportunity": "006",
    "OpportunityHistory": "008",
    "Lead": "00Q",
    "Task": "00T",
    "Event": "00U",
}


def _base62(n: int, width: int) -> str:
    chars = []
    while n:
        n, r = divmod(n, 62)
        chars.append(_B62[r])
    s = "".join(reversed(chars)) or "0"
    if len(s) > width:
        raise ValueError(f"index too large for {width} base62 chars")
    return s.rjust(width, "0")


def checksum_suffix(id15: str) -> str:
    out = []
    for chunk in (id15[0:5], id15[5:10], id15[10:15]):
        bits = sum(1 << i for i, c in enumerate(chunk) if "A" <= c <= "Z")
        out.append(_SUFFIX[bits])
    return "".join(out)


def sfid(obj: str, index: int, seed: int) -> str:
    """18-char Salesforce Id for entity `index` of object `obj`."""
    id15 = KEY_PREFIX[obj] + _base62(seed % (62 * 62), 2) + "0" + _base62(index, 9)
    return id15 + checksum_suffix(id15)


def meeting_id(index: int, seed: int) -> str:
    """Google-Meet-style code, e.g. 'kqr-vbxe-tna', stable per (seed, index)."""
    h = hashlib.sha256(f"meet:{seed}:{index}".encode()).digest()
    letters = "".join("abcdefghijkmnopqrstuvwxyz"[b % 25] for b in h[:10])
    return f"{letters[:3]}-{letters[3:7]}-{letters[7:10]}-{index:05d}"


def ticket_id(index: int) -> str:
    return f"FW-{100000 + index}"
