"""Read-only MIFARE Classic layout, access conditions and capture handling."""
import re

HEX_BYTE = r"[0-9A-Fa-f]{2}"


def identify(atqa, sak):
    if sak == "08" and atqa in {"0004", "0044"}:
        return "1K"
    if sak == "18" and atqa in {"0002", "0042"}:
        return "4K"
    return None


def layout(model):
    count = {"1K": 16, "4K": 40}[model]
    return [range(sector * 4, sector * 4 + 4) if sector < 32
            else range(128 + (sector - 32) * 16, 144 + (sector - 32) * 16)
            for sector in range(count)]


def block_kind(address, blocks):
    if address == blocks[-1]:
        return "trailer"
    return "manufacturer" if address == 0 else "data"


def access_bits(metadata):
    """Decode trailer bytes 6–9, including redundancy checks for bytes 6–8."""
    b6, b7, b8, _ = metadata
    c1, c2, c3 = b7 >> 4, b8 & 15, b8 >> 4
    if (c1 ^ (b6 & 15), c2 ^ (b6 >> 4), c3 ^ (b7 & 15)) != (15, 15, 15):
        raise ValueError("invalid access-bit complements")
    return tuple("".join(str((bits >> group) & 1) for bits in (c1, c2, c3))
                 for group in range(4))


def read_permission(code, trailer_code, is_trailer):
    key_b_is_data = trailer_code in {"000", "001", "010"}
    if is_trailer:
        return "A" if key_b_is_data else "AB"
    if code == "111":
        return ""
    if code in {"011", "101"}:
        return "" if key_b_is_data else "B"
    return "A" if key_b_is_data else "AB"


def read_sector(dev, tag, sector, key_type, key):
    model = identify(tag["atqa"], tag["sak"])
    if model is None or not 0 <= sector < len(layout(model)):
        raise ValueError("Choose a sector in the detected Classic layout")
    if key_type not in {"A", "B"} or not re.fullmatch(f"(?:{HEX_BYTE}){{6}}", key):
        raise ValueError("Supply Key A or B as exactly 12 hexadecimal digits")

    blocks = layout(model)[sector]
    response = dev.ask(f"CLASSIC {tag['uid']} {sector} {key_type} {key.upper()}", timeout=60).split()
    attempt = {"key_type": key_type, "blocks": {}}
    if len(response) == 2 and response[0] == "AUTH" and re.fullmatch(HEX_BYTE, response[1]):
        attempt.update(authentication="failed" if response[1] == "14" else "error",
                       error=f"PN532 status 0x{response[1]}")
    elif response == ["AUTH", "IO"]:
        attempt.update(authentication="error", error="PN532 authentication response unavailable")
    elif len(response) == len(blocks) + 1 and response[0] == "READ":
        attempt["authentication"] = "ok"
        for address, token in zip(blocks, response[1:]):
            entry = {"status": "readable"}
            if re.fullmatch(r"E(?:[0-9A-F]{2}|IO)", token):
                entry = {"status": "inaccessible", "error": (
                    "PN532 block response unavailable" if token == "EIO" else f"PN532 status 0x{token[1:]}")}
            elif token == "-":
                entry = {"status": "unknown", "error": "Read stopped after an earlier block error"}
            elif address == blocks[-1] and re.fullmatch(f"T(?:{HEX_BYTE}){{4}}", token):
                entry["trailer_hex"] = token[1:]
            elif address != blocks[-1] and re.fullmatch(f"(?:{HEX_BYTE}){{16}}", token):
                entry["hex"] = token
            else:
                raise ValueError("Malformed Classic block response")
            attempt["blocks"][str(address)] = entry
    else:
        raise ValueError("Malformed Classic sector response or incompatible firmware")

    tag.setdefault("classic", {}).setdefault(str(sector), {})[key_type] = attempt


def validate_capture(tag):
    if "classic" not in tag:
        return
    model = identify(tag["atqa"], tag["sak"])
    captures = tag["classic"]
    if model is None or not isinstance(captures, dict):
        raise ValueError("Invalid Classic capture")
    sectors = {str(index): blocks for index, blocks in enumerate(layout(model))}
    for sector, attempts in captures.items():
        if sector not in sectors or not isinstance(attempts, dict):
            raise ValueError("Invalid Classic sector")
        blocks = {str(address): block_kind(address, sectors[sector]) for address in sectors[sector]}
        for key_type, attempt in attempts.items():
            if (key_type not in {"A", "B"} or not isinstance(attempt, dict)
                    or attempt.get("key_type") != key_type
                    or attempt.get("authentication") not in ("ok", "failed", "error")
                    or not isinstance(attempt.get("blocks"), dict)
                    or set(attempt) - {"key_type", "authentication", "blocks", "error"}
                    or not isinstance(attempt.get("error", ""), str)):
                raise ValueError("Invalid Classic authentication record")
            for address, entry in attempt["blocks"].items():
                if address not in blocks or not isinstance(entry, dict):
                    raise ValueError("Invalid Classic block address or record")
                if entry.get("status") == "readable":
                    kind = blocks[address]
                    field, length = ("trailer_hex", 4) if kind == "trailer" else ("hex", 16)
                    raw = entry.get(field)
                    valid = (set(entry) == {"status", field} and isinstance(raw, str)
                             and re.fullmatch(f"(?:{HEX_BYTE}){{{length}}}", raw))
                else:
                    valid = (set(entry) == {"status", "error"}
                             and entry.get("status") in ("inaccessible", "unknown")
                             and isinstance(entry["error"], str))
                if not valid:
                    raise ValueError("Invalid Classic block contents")


MEMORY_HEADER = "Location                     | Hex bytes                                       | ASCII"


def memory_row(location, raw, status=""):
    if raw is None:
        hex_bytes, ascii_text = "—", "unavailable"
    else:
        hex_bytes = " ".join("--" if byte is None else f"{byte:02X}" for byte in raw)
        ascii_text = "".join("-" if byte is None else chr(byte) if 32 <= byte < 127 else "."
                             for byte in raw)
    annotation = f"  ({status})" if status else ""
    return f"{location:<28} | {hex_bytes:<47} | {ascii_text}{annotation}"


def describe(tag, model, only_sector=None):
    sectors = layout(model)
    total = sum(map(len, sectors))
    captured = tag.get("classic", {})
    verified = any(a.get("authentication") == "ok" for s in captured.values() for a in s.values())
    confidence = "likely from ATQA/SAK"
    if verified:
        confidence = "Classic-compatible authentication confirmed; capacity inferred from ATQA/SAK"
    print(f"MIFARE Classic {model} or compatible ({confidence})")
    print(f"{len(sectors)} sectors | {total} blocks × 16 bytes | {total * 16} bytes total")
    readable = {}
    for sector in captured.values():
        for attempt in sector.values():
            for address, block in attempt["blocks"].items():
                if "hex" in block:
                    readable[address] = 16
                elif "trailer_hex" in block:
                    readable[address] = 4
    print(f"Bytes read: {sum(readable.values())} | Total capacity: {total * 16} bytes")
    print("Each sector requires its authorized Key A or Key B. Choose Read sector to enter an authorized key.")
    for sector, blocks in enumerate(sectors):
        if only_sector is not None and sector != only_sector:
            continue
        attempts = captured.get(str(sector), {})
        label = ", ".join(f"Key {key} {attempt['authentication']}" +
                          (f" ({attempt['error']})" if "error" in attempt else "")
                          for key, attempt in sorted(attempts.items()))
        start = blocks[0] + int(sector == 0)
        print(f"  Sector {sector:02d} | blocks {blocks[0]:03d}–{blocks[-1]:03d} | "
              f"{len(blocks)} × 16 B | data {start}–{blocks[-2]}, trailer {blocks[-1]}"
              + (", manufacturer 0" if sector == 0 else ""))
        print(f"    Authentication: {label or 'not attempted; contents protected by sector authentication'}")
        print(MEMORY_HEADER)
        trailer = next((entry["trailer_hex"] for attempt in attempts.values()
                        if "trailer_hex" in (entry := attempt["blocks"].get(str(blocks[-1]), {}))), None)
        groups = None
        if trailer:
            print(f"    Trailer bytes 6–9: {trailer} (access bits + GPB); key fields omitted")
            try:
                groups = access_bits(bytes.fromhex(trailer))
            except ValueError as exc:
                print(f"    Trailer: {exc}")
        for address in blocks:
            kind = block_kind(address, blocks)
            entries = [(key, attempt["blocks"].get(str(address), {})) for key, attempt in attempts.items()]
            status = "access unknown" if any(a["authentication"] == "ok" for a in attempts.values()) else "protected (authentication required)"
            if groups:
                offset = address - blocks[0]
                group = offset if len(blocks) == 4 else offset // 5
                allowed = read_permission(groups[group], groups[3], kind == "trailer")
                status = f"access {groups[group]}, read Key {' or '.join(allowed)}" if allowed else f"access {groups[group]}, inaccessible by either key"
            location = f"Block {address:03d} {kind}"
            rows = []
            errors = []
            for key, entry in entries:
                if "hex" in entry:
                    rows.append(memory_row(f"{location} ({key})", bytes.fromhex(entry["hex"]), status))
                elif "trailer_hex" in entry:
                    metadata = tuple(bytes.fromhex(entry["trailer_hex"]))
                    raw = (None,) * 6 + metadata + (None,) * 6
                    rows.append(memory_row(f"{location} ({key})", raw, f"key fields omitted; {status}"))
                elif "error" in entry:
                    errors.append(f"Key {key} {entry['status']}: {entry['error']}")
            if not rows:
                rows.append(memory_row(location, None, status))
            for row in rows:
                print(row)
            for error in errors:
                print(f"  {location}: {error}")
