import unittest

from pipeline.common.concept_validation import parse_concept_response


class ConceptValidationTests(unittest.TestCase):
    def test_parse_json_array_and_dedup(self):
        self.assertEqual(
            parse_concept_response('["  Tổ chức  ", "Tổ chức", "", "Công ty"]'),
            ["Tổ chức", "Công ty"],
        )

    def test_parse_fenced_json_array(self):
        self.assertEqual(
            parse_concept_response('```json\n["Sự kiện", "Hoạt động"]\n```'),
            ["Sự kiện", "Hoạt động"],
        )

    def test_parse_object_with_concepts(self):
        self.assertEqual(
            parse_concept_response('{"concepts": ["Quan hệ nhân quả"]}'),
            ["Quan hệ nhân quả"],
        )

    def test_parse_comma_separated_fallback(self):
        self.assertEqual(
            parse_concept_response("thực thể, tổ chức, địa danh"),
            ["thực thể", "tổ chức", "địa danh"],
        )

    def test_reject_non_string_array(self):
        with self.assertRaises(ValueError):
            parse_concept_response('["ok", 1]')


if __name__ == "__main__":
    unittest.main()
