"""Unit tests for bot.viewer.tags."""

import unittest

from bot.viewer.tags import (
    CAD_NS,
    SPLINE_NS,
    decode,
    encode,
    is_namespaced,
    parse_cad_local_id,
    prefix,
)


class TestTagNamespacing(unittest.TestCase):
    def test_encode_cad(self):
        self.assertEqual(encode(CAD_NS, 42), "cad:42")

    def test_encode_spline(self):
        tag = encode(SPLINE_NS, "curve-abc")
        self.assertEqual(tag, "spline:curve-abc")

    def test_decode_round_trip(self):
        tag = encode(CAD_NS, 7)
        self.assertEqual(decode(tag), (CAD_NS, "7"))

    def test_decode_invalid(self):
        self.assertIsNone(decode("not-a-tag"))
        self.assertIsNone(decode(""))
        self.assertIsNone(decode("cad:"))
        self.assertIsNone(decode(":42"))

    def test_prefix(self):
        self.assertEqual(prefix("cad:99"), CAD_NS)
        self.assertIsNone(prefix("bad"))

    def test_is_namespaced(self):
        self.assertTrue(is_namespaced("cad:1"))
        self.assertFalse(is_namespaced("1"))

    def test_parse_cad_local_id_valid(self):
        self.assertEqual(parse_cad_local_id("cad:42"), 42)

    def test_parse_cad_local_id_wrong_namespace(self):
        self.assertIsNone(parse_cad_local_id("spline:curve-x"))

    def test_parse_cad_local_id_invalid_int(self):
        self.assertIsNone(parse_cad_local_id("cad:not-int"))


if __name__ == "__main__":
    unittest.main()
