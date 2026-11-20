import contextlib
import io
import json
import sys
import unittest
from unittest.mock import Mock, patch

import lab


class Reader:
    def __init__(self, prefix=b"", version="0004040201000F03"):
        self.version = version
        self.data = bytearray(45 * 4)
        self.data[12:16] = bytes.fromhex("E1101200")
        self.data[167] = 255
        image = prefix + bytes.fromhex("0300FE")
        self.data[16:16+len(image)] = image
        self.writes = []

    def ask(self, command):
        op, *args = command.split()
        if op == "SCAN":
            return f"04010203040506 0044 00 {self.version}"
        if op == "PAGE":
            start = int(args[0])*4
            return self.data[start:start+4].hex().upper()
        uid, page, value = args
        assert op == "WRITE" and uid == "04010203040506"
        start = int(page)*4
        self.writes.append(int(page))
        self.data[start:start+4] = bytes.fromhex(value)
        return "verified"


class CopyTests(unittest.TestCase):
    def setUp(self):
        reader = Reader()
        image = bytes.fromhex("0308D101045402656E78FE")
        reader.data[16:16+len(image)] = image
        self.source = lab.inspect(reader)
        self.source["uid"] = "04000000000000"

    def test_confirm_copy_and_verify(self):
        for prefix in (b"", bytes.fromhex("0103A00C34")):
            reader = Reader(prefix)
            before = reader.data[:]
            with patch("builtins.input", return_value="cancel"), contextlib.redirect_stdout(io.StringIO()):
                lab.copy(reader, self.source)
            self.assertEqual(reader.data, before)
            with patch("builtins.input", return_value="WRITE 04010203040506"), contextlib.redirect_stdout(io.StringIO()):
                lab.copy(reader, self.source)
            self.assertEqual(lab.copy_image(lab.inspect(reader)), lab.copy_image(self.source))
            self.assertEqual(reader.data[16:16+len(prefix)], prefix)
            self.assertEqual(reader.writes[0], reader.writes[-1])

    def test_reject_protection_and_missing_pages(self):
        reader = Reader()
        reader.data[167] = 4
        with self.assertRaises(ValueError):
            lab.copy_image(lab.inspect(reader), destination=True)
        self.source["pages"]["8"] = None
        with self.assertRaises(ValueError):
            lab.copy_image(self.source)

    def test_ndef(self):
        self.assertEqual(lab.records(bytes.fromhex("D101045402656E78"))[0]["decoded"], "x")
        with self.assertRaises(ValueError):
            lab.records(bytes.fromhex("D101045402656E"))

class DetectionAndActionsTests(unittest.TestCase):
    def test_ntag213_screenshot_and_partial_read(self):
        reader = Reader(version="0004040201010F03")
        ndef = bytes.fromhex("0308D101045402656E78FE")
        reader.data[16:16 + len(ndef)] = ndef
        scan = lab.inspect(reader)
        self.assertEqual(lab.identify(scan), ("ntag", ("NTAG213", 40)))
        self.assertEqual(lab.available_actions(scan)["copy"], "Copy NDEF")
        capture = json.loads(json.dumps(scan))
        self.assertEqual(lab.available_actions(scan), lab.available_actions(capture))
        ask = reader.ask
        reader.ask = lambda command: "bad" if command == "PAGE 20" else ask(command)
        partial = lab.inspect(reader)
        self.assertIsNone(partial["pages"]["20"])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            lab.describe(partial)
        report = output.getvalue()
        self.assertIn("Bytes read: 168 | Total capacity: 180 bytes", report)
        self.assertIn("masked / omitted", report)
        self.assertIn("unavailable", report)
        self.assertIn('"decoded": "x"', report)
        self.assertNotIn("copy", lab.available_actions(partial))

    def test_ambiguous_and_unknown_keep_raw_identity(self):
        for reply in ("04010203040506 0044 00 0004040201010F99",
                      "04010203040506 0004 08 0004040201010F03"):
            dev = Mock()
            dev.ask.return_value = reply
            tag = lab.inspect(dev)
            dev.ask.assert_called_once_with("SCAN")
            self.assertEqual(set(lab.available_actions(tag)), {"scan", "show", "save", "load", "quit"})
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                lab.describe(tag)
            self.assertIn("Memory layout unknown", output.getvalue())
            for field in reply.split():
                self.assertIn(field, output.getvalue())

    def test_model_action_rules(self):
        self.assertEqual(set(lab.available_actions(None)), {"scan", "load", "quit"})
        for version, model in (("0004040201001103", "NTAG215"), ("0004040201001303", "NTAG216")):
            tag = {"atqa": "0044", "sak": "00", "version": version, "pages": {}}
            self.assertEqual(lab.identify(tag)[1][0], model)
            self.assertNotIn("copy", lab.available_actions(tag))
        for atqa, sak in (("0004", "08"), ("0002", "18")):
            tag = {"atqa": atqa, "sak": sak, "version": "-", "pages": {}}
            self.assertIn("read", lab.available_actions(tag))
            self.assertNotIn("copy", lab.available_actions(tag))

    def test_menu_refreshes_after_scan(self):
        dev = Mock()
        dev.ask.side_effect = ["32010607", "04010203040506 0044 00 -"]
        with patch.object(sys, "argv", ["nfc-lab", "/dev/mock"]), \
                patch.object(sys.stdin, "isatty", return_value=True), \
                patch.object(sys.stdout, "isatty", return_value=True), \
                patch.object(lab, "usb_port", return_value=contextlib.nullcontext()), \
                patch.object(lab, "Device", return_value=dev), \
                patch.object(lab, "choose", side_effect=[0, 4]) as menu, \
                patch("builtins.print"):
            lab.main()
        self.assertEqual(menu.call_args_list[0].args[0], ["Scan", "Load", "Quit"])
        self.assertEqual(menu.call_args_list[1].args[0], ["Scan", "Show", "Save", "Load", "Quit"])
        self.assertEqual(dev.ask.call_count, 2)

    def test_type2_fallback_is_read_only(self):
        dev = Mock()
        dev.ask.return_value = (
            "04AE4CFA962394 0044 00 - 01 1 00 17 "
            "04AE4C6EFA9623945B480000E110120F"
        )
        tag = lab.inspect(dev)
        dev.ask.assert_called_once_with("SCAN")
        self.assertEqual(tag["pages"]["3"], "E110120F")
        self.assertNotIn("copy", lab.available_actions(tag))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            lab.describe(json.loads(json.dumps(tag)))
        for message in ("status 0x01 | response length 1", "status 0x00 | response length 17",
                        "Bytes read: 16", "Page 03", "144-byte data area", "physical capacity unknown"):
            self.assertIn(message, output.getvalue())
        self.assertIsNone(lab.capability_size(bytes.fromhex("00101200")))

    def test_failed_fallback_preserves_identification(self):
        for tail in ("RESELECT", "01 1 -", "00 16 -", "- -1 -"):
            dev = Mock()
            dev.ask.return_value = f"04AE4CFA962394 0044 00 - - -1 {tail}"
            tag = lab.inspect(dev)
            self.assertEqual(tag["uid"], "04AE4CFA962394")
            self.assertEqual(tag["pages"], {})
            self.assertIn("READ page 00", tag["diagnostics"])
