#!/usr/bin/env python3
"""Offline NFC Lab console. Python 3.9+ standard library."""
import argparse
import contextlib
import fcntl
import getpass
import os
import re
import select
import sys
import termios
import time
import tty
import warnings
import json
from importlib import metadata
from pathlib import Path

import classic

MODELS = {
    "0004040201000F03": ("NTAG213", 40),
    "0004040201010F03": ("NTAG213", 40),
    "0004040201001103": ("NTAG215", 130),
    "0004040201001303": ("NTAG216", 226),
}
PREFIXES = ["", "http://www.", "https://www.", "http://", "https://", "tel:", "mailto:"]


@contextlib.contextmanager
def usb_port(path):
    with open(path, "r+b", buffering=0, opener=lambda name, flags: os.open(
        name, flags | os.O_NOCTTY | os.O_NONBLOCK
    )) as port:
        fcntl.ioctl(port, termios.TIOCEXCL)
        original = termios.tcgetattr(port)
        try:
            tty.setraw(port)
            settings = termios.tcgetattr(port)
            settings[4:6] = [termios.B115200, termios.B115200]
            termios.tcsetattr(port, termios.TCSANOW, settings)
            termios.tcflush(port, termios.TCIFLUSH)
            yield port
        finally:
            termios.tcsetattr(port, termios.TCSANOW, original)


class Device:
    def __init__(self, port):
        self.port = port

    def ask(self, command, timeout=5):
        request = (command + "\n").encode("ascii")
        if not select.select([], [self.port], [], 2)[1] or self.port.write(request) != len(request):
            raise OSError("Incomplete USB write. Reconnect before retrying.")
        deadline = time.monotonic() + timeout
        line = bytearray()
        while len(line) < 1024 and not line.endswith(b"\n"):
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.port], [], [], remaining)[0]:
                break
            chunk = self.port.read(1)
            if not chunk:
                break
            line.extend(chunk)
        if not line.endswith(b"\n"):
            raise OSError("USB timeout or incomplete response. Reconnect before retrying.")
        status, _, data = line.decode("ascii").strip().partition(" ")
        if status == "ERR":
            raise ValueError(data)
        if status != "OK":
            raise OSError("Unexpected USB response. Reconnect before retrying.")
        return data


def identify(tag):
    """Return a supported family and layout only for consistent evidence."""
    atqa, sak, version = (tag[field].upper() for field in ("atqa", "sak", "version"))
    if atqa == "0044" and sak == "00" and version in MODELS:
        return "ntag", MODELS[version]
    model = classic.identify(atqa, sak)
    if model and version == "-":
        return "classic", model
    return None, None


def scan_identity(dev):
    fields = dev.ask("SCAN").upper().split()
    patterns = (r"(?:[0-9A-Fa-f]{2}){4,10}", r"[0-9A-Fa-f]{4}",
                r"[0-9A-Fa-f]{2}", r"-|(?:[0-9A-Fa-f]{2}){1,54}")
    if len(fields) not in (4, 6, 7, 9) or not all(re.fullmatch(pattern, value)
                                  for pattern, value in zip(patterns, fields)):
        raise ValueError("Malformed scan response")
    identity = dict(zip(("uid", "atqa", "sak", "version"), fields[:4]))
    diagnostics = {}
    if len(fields) >= 6:
        diagnostics["GET_VERSION"] = exchange_diagnostic(*fields[4:6])
    fallback = None
    if len(fields) == 7 and fields[6] == "RESELECT":
        diagnostics["READ page 00"] = {"error": "same tag could not be reselected"}
    elif len(fields) == 9:
        status, length, data = fields[6:]
        diagnostics["READ page 00"] = exchange_diagnostic(status, length)
        if status == "00" and length == "17" and re.fullmatch(r"[0-9A-F]{32}", data):
            fallback = data
        elif data != "-":
            raise ValueError("Malformed fallback READ response")
    elif len(fields) == 7:
        raise ValueError("Malformed scan diagnostics")
    return identity, diagnostics, fallback


def exchange_diagnostic(status, length):
    if not re.fullmatch(r"-|[0-9A-F]{2}", status) or not re.fullmatch(r"-1|[0-9]{1,2}", length):
        raise ValueError("Malformed PN532 exchange diagnostics")
    return {"status": None if status == "-" else status, "length": int(length) if length != "-1" else None}


def page_bytes(value):
    if isinstance(value, str) and re.fullmatch(r"[0-9A-Fa-f]{8}", value):
        return bytes.fromhex(value)
    return None


def inspect(dev):
    identity, diagnostics, fallback = scan_identity(dev)
    tag = dict(format="nfc-lab/1", **identity, pages={})
    if diagnostics:
        tag["diagnostics"] = diagnostics
    family, model = identify(tag)
    if family == "ntag":
        _, lock = model
        for page in range(lock + 3):
            try:
                value = dev.ask(f"PAGE {page}")
            except ValueError:
                value = None
            tag["pages"][str(page)] = value if page_bytes(value) is not None else None
        if scan_identity(dev)[0] != identity:
            raise ValueError("Tag changed during inspection. Discarded capture.")
    elif fallback and type2_candidate(tag):
        tag["pages"] = {str(page): fallback[page * 8:page * 8 + 8] for page in range(4)}
    return tag


def records(message):
    offset = 0
    result = []
    while offset < len(message):
        def take(n):
            nonlocal offset
            if offset + n > len(message):
                raise ValueError("Truncated NDEF record")
            start = offset
            offset += n
            return message[start:offset]

        flags, typelen = take(2)
        if bool(flags & 128) != (not result) or flags & 32:
            raise ValueError("Invalid message boundary or unsupported chunked NDEF")
        size = int.from_bytes(take(1 if flags & 16 else 4), "big")
        idlen = take(1)[0] if flags & 8 else 0
        typ, ident, payload = take(typelen), take(idlen), take(size)
        decoded = None
        if flags & 7 == 1 and typ == b"T" and payload:
            langlen = payload[0] & 63
            if langlen + 1 <= len(payload):
                raw = payload[1 + langlen:]
                codec = "utf-8"
                if payload[0] & 128:
                    codec = "utf-16" if raw.startswith((b"\xfe\xff", b"\xff\xfe")) else "utf-16-be"
                decoded = raw.decode(codec, errors="replace")
        if flags & 7 == 1 and typ == b"U" and payload and payload[0] < len(PREFIXES):
            decoded = PREFIXES[payload[0]] + payload[1:].decode("utf-8", errors="replace")
        result.append(dict(tnf=flags & 7, type=typ.hex(), id=ident.hex(), payload=payload.hex(), decoded=decoded))
        if flags & 64:
            if offset != len(message):
                raise ValueError("Data after final NDEF record")
            return result
    if result:
        raise ValueError("Missing NDEF end flag")
    return result


def memory(tag, start, end):
    parts = [page_bytes(tag["pages"].get(str(i))) for i in range(start, end)]
    if any(part is None for part in parts):
        raise ValueError("Required pages unavailable")
    return b"".join(parts)


def tlvs(data):
    pos = 0
    while pos < len(data):
        kind = data[pos]
        pos += 1
        if kind == 0:
            continue
        if kind == 254:
            return
        if pos >= len(data):
            raise ValueError("Missing TLV length")
        size = data[pos]
        pos += 1
        if size == 255:
            if pos+2 > len(data):
                raise ValueError("Missing extended length")
            size = int.from_bytes(data[pos:pos+2], "big")
            pos += 2
        if pos+size > len(data):
            raise ValueError("Truncated TLV")
        yield kind, data[pos:pos+size]
        pos += size


def type2_candidate(tag):
    return (len(tag["uid"]) == 14 and tag["atqa"].upper() == "0044"
            and tag["sak"] == "00" and tag["version"] == "-")


def capability_size(cc):
    if cc and cc[0] == 0xE1 and cc[1] >> 4 == 1 and cc[2] and cc[3] in (0x00, 0x0F):
        return cc[2] * 8
    return None


def describe(tag):
    print(f"ISO 14443-A 106 kbit/s | UID {tag['uid']} | ATQA {tag['atqa']} | SAK {tag['sak']}")
    print("GET_VERSION:", tag["version"] if tag["version"] != "-" else "unavailable")
    for operation, details in tag.get("diagnostics", {}).items():
        if "error" in details:
            print(f"{operation}: {details['error']}; READ not attempted")
        else:
            status = f"0x{details['status']}" if details["status"] is not None else "unavailable"
            length = details["length"] if details["length"] is not None else "unavailable"
            print(f"{operation}: PN532 status {status} | response length {length} (including status)")
    family, model = identify(tag)
    if family == "classic":
        classic.describe(tag, model)
        return
    if family != "ntag":
        if type2_candidate(tag) and tag["pages"]:
            pages = [page_bytes(tag["pages"].get(str(page))) for page in range(4)]
            print("Type 2 page probe | Exact model and total physical capacity unknown")
            print(f"Bytes read: {sum(len(raw) for raw in pages if raw is not None)}")
            print(classic.MEMORY_HEADER)
            for page, raw in enumerate(pages):
                print(classic.memory_row(f"Page {page:02X}", raw))
            size = capability_size(pages[3])
            if size is not None:
                print(f"Type 2 Capability Container declares a {size}-byte data area")
            else:
                print("No valid Type 2 Capability Container found on page 03")
        else:
            print("Memory layout unknown")
        return
    name, lock = model
    pages = [page_bytes(tag["pages"].get(str(page))) for page in range(lock + 3)]
    read_count = sum(len(raw) for raw in pages if raw is not None)
    print(f"{name} (likely from GET_VERSION and Type A metadata) | reported manufacturer NXP")
    print(f"Bytes read: {read_count} | Total capacity: {(lock + 5) * 4} bytes | "
          f"User area: {(lock - 4) * 4} bytes")
    print(classic.MEMORY_HEADER)
    for page, raw in enumerate(pages):
        print(classic.memory_row(f"Page {page:02X}", raw))
    for page, field in ((lock + 3, "Password"), (lock + 4, "PACK page")):
        print(classic.memory_row(f"Page {page:02X}", (None,) * 4, f"{field}: masked / omitted"))
    try:
        print("Static lock:", memory(tag, 2, 3)[2:].hex(), "CC:", memory(tag, 3, 4).hex())
        cfg = memory(tag, lock, lock+3)
        print(f"Dynamic lock: {cfg[:3].hex()} | AUTH0: {cfg[7]:02X} | ACCESS: {cfg[8]:02X}")
        if cfg[7] < lock+5:
            print("Password protection from page", cfg[7], "(read/write)" if cfg[8]&128 else "(write)")
    except ValueError as exc:
        print("Configuration:", exc)
    try:
        cc = memory(tag, 3, 4)
        if cc[0] != 0xE1:
            raise ValueError("No NFC Forum Type 2 capability container")
        size = min(cc[2] * 8, (lock - 4) * 4)
        prefix = bytearray()
        for raw in pages[4:lock]:
            if raw is None:
                break
            prefix.extend(raw)
        for kind, value in tlvs(prefix[:size]):
            print(f"TLV {kind:02X}:", json.dumps(records(value)) if kind == 3 else value.hex())
        if len(prefix) < size:
            print("NDEF inspection: later bytes unavailable")
    except ValueError as exc:
        print("NDEF inspection:", exc)


def copy_image(tag, destination=False):
    if identify(tag) != ("ntag", ("NTAG213", 40)) or memory(tag, 3, 4) != bytes.fromhex("E1101200"):
        raise ValueError("Copy requires a standard NTAG213 layout")
    if destination:
        cfg = memory(tag, 40, 42)
        if any(memory(tag, 2, 3)[2:] + cfg[:3]) or cfg[7] != 255 or cfg[4] & 192:
            raise ValueError("Destination locked, mirrored, or password-configured")
    raw = memory(tag, 4, 40)
    if destination and not any(raw):
        return raw
    prefix = bytes.fromhex("0103A00C34")
    body = raw[len(prefix):] if raw.startswith(prefix) else raw
    items = list(tlvs(body))
    if len(items) != 1 or items[0][0] != 3 or body[0] != 3:
        raise ValueError("Copy supports one NDEF TLV, optionally after the standard NTAG213 lock TLV")
    payload = items[0][1]
    records(payload)
    if destination:
        return raw
    out = bytes([3, len(payload)]) + payload
    return out + (b'\xfe' if len(out) < 144 else b'')


def copy(dev, source):
    image = copy_image(source)
    target = inspect(dev)
    uid = target["uid"]
    old = copy_image(target, destination=True)
    prefix = bytes.fromhex("0103A00C34")
    if old.startswith(prefix):
        image = prefix + image
        if len(image) == 145 and image[6] == 137:
            image = image[:-1]
        if len(image) > 144:
            raise ValueError("NDEF exceeds destination capacity")
    if uid == source["uid"]:
        raise ValueError("Present a different destination tag")
    end = (len(image)+3)//4*4
    final = image + old[len(image):end]
    print(f"Replace destination NDEF on {uid}, user pages 4..{3+end//4}.")
    print("Excluded: UID, locks, CC, configuration, password, PACK and unused source bytes.")
    if input(f"Type WRITE {uid} to confirm: ") != f"WRITE {uid}":
        print("Cancelled")
        return
    current = inspect(dev)
    if current != target:
        raise ValueError("Destination changed since preview")
    if old[:end] != final:
        # Publish an empty TLV while updating, then commit its length last.
        def write(page, data):
            dev.ask(f"WRITE {uid} {page} {data.hex().upper()}")
        start = 4 if old.startswith(prefix) else 0
        staged = bytes.fromhex('340300fe') if start else bytes.fromhex('0300fe00')
        write(4+start//4, staged)
        for i in range(start+4, end, 4):
            if old[i:i+4] != final[i:i+4]:
                write(4+i//4, final[i:i+4])
        write(4+start//4, final[start:start+4])
    check = inspect(dev)
    if check["uid"] != uid or memory(check, 4, 4+end//4) != final:
        raise ValueError("Final read-back mismatch")
    print("Verified destination NDEF by read-back.")


def available_actions(tag):
    actions = {"scan": "Scan"}
    if tag is not None:
        actions["show"] = "Show"
        if identify(tag)[0] == "classic":
            actions["read"] = "Read sector"
        actions["save"] = "Save"
    actions["load"] = "Load"
    if tag is not None and identify(tag) == ("ntag", ("NTAG213", 40)):
        try:
            copy_image(tag)
        except ValueError:
            pass
        else:
            actions["copy"] = "Copy NDEF"
    actions["quit"] = "Quit"
    return actions


def choose(options, selected=0):
    """Select an option on one terminal line, leaving command output in scrollback."""
    fd = sys.stdin.fileno()
    original = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            menu = "  ".join(f"[{label}]" if i == selected else label
                             for i, label in enumerate(options))
            print(f"\r\x1b[2K{menu}", end="", flush=True)
            key = os.read(fd, 1)
            if key in (b"\r", b"\n"):
                return selected
            if key in (b"", b"\x04"):
                raise EOFError
            if key == b"\x1b":
                sequence = b""
                for _ in range(2):
                    if not select.select([fd], [], [], 0.1)[0]:
                        break
                    sequence += os.read(fd, 1)
                if sequence in (b"[A", b"[D", b"OA", b"OD"):
                    selected = (selected - 1) % len(options)
                elif sequence in (b"[B", b"[C", b"OB", b"OC"):
                    selected = (selected + 1) % len(options)
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, original)
        print("\r\x1b[2K", end="", flush=True)


def main():
    parser = argparse.ArgumentParser()
    try:
        release = metadata.version("nfc-lab")
    except metadata.PackageNotFoundError:
        release = "uninstalled source checkout"
    parser.add_argument("--version", action="version", version=f"nfc-lab {release}")
    parser.add_argument("port", nargs="?", help="USB serial device (automatically selected when unique)")
    for pin, default in (("sda", 8), ("scl", 9)):
        parser.add_argument("--"+pin, default=default, type=int, choices=range(11), help="GPIO number (default: %(default)s)")
    args = parser.parse_args()
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.exit(1, "NFC Lab requires an interactive terminal for the arrow-key menu.\n")
    if args.port is None:
        ports = sorted(Path("/dev").glob("cu.usbmodem*"))
        if not ports:
            parser.exit(1, "No USB modem found. Connect the ESP32 or specify its serial port.\n")
        if len(ports) > 1:
            parser.exit(1, "Choose a port: nfc-lab PORT\n" + "\n".join(map(str, ports)) + "\n")
        args.port = ports[0]
    print(f"Opening {args.port} (SDA {args.sda}, SCL {args.scl})", flush=True)
    with usb_port(args.port) as port:
        dev = Device(port)
        try:
            version = dev.ask(f"INIT {args.sda} {args.scl}", timeout=12)
        except OSError as exc:
            raise OSError(f"{exc} Check that nfc_lab.ino was uploaded with USB CDC On Boot enabled.") from exc
        print("PN532 IC/version/revision/support:", version)
        tag = None
        selected = "scan"
        print("Use arrow keys to move and Enter to select.")
        while True:
            try:
                actions = available_actions(tag)
                names = list(actions)
                index = names.index(selected) if selected in actions else 0
                selected = names[choose(list(actions.values()), index)]
                if selected == "quit":
                    break
                if selected == "scan":
                    tag = None
                    tag = inspect(dev)
                    describe(tag)
                elif selected in ("load", "save"):
                    filename = input("Capture file (blank to cancel): ")
                    if not filename:
                        continue
                    if selected == "save":
                        with Path(filename).open("x") as output:
                            json.dump(tag, output, indent=2)
                        continue
                    candidate = json.loads(Path(filename).read_text())
                    if not isinstance(candidate, dict) or candidate.get("format") != "nfc-lab/1":
                        raise ValueError("Unknown capture format")
                    if not isinstance(candidate.get("pages"), dict) or not all(isinstance(candidate.get(k), str) for k in ("uid","atqa","sak","version")):
                        raise ValueError("Invalid capture fields")
                    classic.validate_capture(candidate)
                    describe(candidate)
                    tag = candidate
                elif selected == "read":
                    sector_input = input("Sector number (blank to cancel): ").strip()
                    if not sector_input:
                        continue
                    sector = int(sector_input, 10)
                    _, model = identify(tag)
                    if not 0 <= sector < len(classic.layout(model)):
                        raise ValueError("Choose a sector in the detected Classic layout")
                    key_choice = choose(("Key A", "Key B", "Cancel"))
                    if key_choice == 2:
                        continue
                    key_type = ("A", "B")[key_choice]
                    with warnings.catch_warnings():
                        warnings.simplefilter("error", getpass.GetPassWarning)
                        try:
                            key = getpass.getpass(f"Key {key_type} for sector {sector} (12 hex digits): ")
                        except getpass.GetPassWarning as exc:
                            raise ValueError("A terminal with hidden input is required") from exc
                    try:
                        classic.read_sector(dev, tag, sector, key_type, key)
                    finally:
                        del key
                    classic.describe(tag, model, only_sector=sector)
                elif selected == "copy":
                    copy(dev, tag)
                elif selected == "show":
                    describe(tag)
            except (ValueError, FileNotFoundError, FileExistsError, PermissionError) as exc:
                print(exc)
            except EOFError:
                break


def cli():
    try:
        main()
    except (OSError, ValueError, KeyboardInterrupt) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    cli()
