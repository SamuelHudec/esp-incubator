import contextlib
import io
import json
import unittest
from unittest.mock import Mock

import classic
import lab


class ClassicTests(unittest.TestCase):
    def test_layout(self):
        for model, sector_count, block_count in (("1K", 16, 64), ("4K", 40, 256)):
            sectors = classic.layout(model)
            self.assertEqual(len(sectors), sector_count)
            self.assertEqual([block for sector in sectors for block in sector], list(range(block_count)))
        sectors = classic.layout("4K")
        self.assertEqual(sectors[31], range(124, 128))
        self.assertEqual(sectors[32], range(128, 144))
        self.assertEqual(sectors[39], range(240, 256))
        self.assertEqual(classic.block_kind(255, sectors[39]), "trailer")

    def test_access_bits(self):
        self.assertEqual(classic.access_bits(bytes.fromhex("FF078069")), ("000", "000", "000", "001"))
        with self.assertRaises(ValueError):
            classic.access_bits(bytes.fromhex("FE078069"))
        self.assertEqual(classic.read_permission("011", "011", False), "B")
        self.assertEqual(classic.read_permission("011", "001", False), "")
        self.assertEqual(classic.read_permission("111", "011", False), "")

    def test_scan_without_keys(self):
        dev = Mock()
        dev.ask.return_value = "11223344 0004 08 -"
        tag = lab.inspect(dev)
        dev.ask.assert_called_once_with("SCAN")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            lab.describe(tag)
        self.assertIn("likely from ATQA/SAK", output.getvalue())
        self.assertIn("16 sectors | 64 blocks × 16 bytes | 1024 bytes", output.getvalue())
        self.assertIn("Sector 15 | blocks 060–063", output.getvalue())
        self.assertEqual(classic.identify("0042", "18"), "4K")
        self.assertIsNone(classic.identify("0004", "00"))

    def test_dump_with_reads_and_auth_failure(self):
        dev = Mock()
        tag = dict(format="nfc-lab/1", uid="11223344", atqa="0004", sak="08", version="-", pages={})
        raw = "00112233445566778899aabbccddeeff"
        dev.ask.side_effect = [f"READ {raw} E01 - TFF078069", "AUTH 14", "READ short"]
        classic.read_sector(dev, tag, 0, "A", "AABBCCDDEE00")
        classic.read_sector(dev, tag, 0, "B", "112233445566")
        with self.assertRaises(ValueError):
            classic.read_sector(dev, tag, 0, "B", "112233445566")
        dump = json.dumps(tag)
        self.assertNotIn("AABBCCDDEE00", dump)
        self.assertNotIn("112233445566", dump.upper().replace(raw.upper(), ""))
        loaded = json.loads(dump)
        classic.validate_capture(loaded)
        self.assertEqual(loaded, tag)
        attempts = loaded["classic"]["0"]
        self.assertEqual(attempts["B"]["authentication"], "failed")
        blocks = attempts["A"]["blocks"]
        self.assertEqual(blocks["0"]["hex"], raw)
        self.assertEqual(blocks["1"]["error"], "PN532 status 0x01")
        self.assertEqual(blocks["2"]["status"], "unknown")
        self.assertEqual(blocks["3"]["trailer_hex"], "FF078069")
        blocks["3"]["hex"] = raw
        with self.assertRaises(ValueError):
            classic.validate_capture(loaded)
