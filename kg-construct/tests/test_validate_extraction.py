from __future__ import annotations

import unittest

from pipeline.common.extraction_validation import parse_json_payload, validate_stage_payload


class ExtractionParserTests(unittest.TestCase):
    def test_parse_json_payload_accepts_markdown_fenced_array(self) -> None:
        parsed = parse_json_payload(
            """```json
            [{"Head": "A", "Relation": "liên quan", "Tail": "B"}]
            ```"""
        )

        self.assertEqual(parsed[0]["Head"], "A")

    def test_parse_json_payload_extracts_first_json_fragment(self) -> None:
        parsed = parse_json_payload(
            'Kết quả: [{"Event": "A diễn ra.", "Entity": ["A", "B"]}] Cảm ơn.'
        )

        self.assertEqual(parsed[0]["Event"], "A diễn ra.")

    def test_validate_triple_stage_strips_and_normalizes_strings(self) -> None:
        normalized = validate_stage_payload(
            "entity_relation",
            [{"Head": "  Đại học   Quốc gia  ", "Relation": "  quản lý ", "Tail": " UET "}],
        )

        self.assertEqual(
            normalized,
            [{"Head": "Đại học Quốc gia", "Relation": "quản lý", "Tail": "UET"}],
        )

    def test_validate_event_entity_deduplicates_entities(self) -> None:
        normalized = validate_stage_payload(
            "event_entity",
            [{"Event": "UET tổ chức hội thảo.", "Entity": ["UET", "UET", "hội thảo"]}],
        )

        self.assertEqual(normalized[0]["Entity"], ["UET", "hội thảo"])

    def test_validate_stage_payload_rejects_wrong_shape(self) -> None:
        with self.assertRaises(ValueError):
            validate_stage_payload("event_relation", {"Head": "A"})


if __name__ == "__main__":
    unittest.main()
