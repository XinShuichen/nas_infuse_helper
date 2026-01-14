# Copyright (c) 2025 Trae AI. All rights reserved.

import unittest
from src.core.renamer import Renamer

class TestRenamerSanitization(unittest.TestCase):
    def setUp(self):
        self.renamer = Renamer()

    def test_sanitize_colon(self):
        # Blade Runner 2049: The Final Cut -> Blade Runner 2049 - The Final Cut
        self.assertEqual(
            self.renamer.sanitize_for_samba("Blade Runner 2049: The Final Cut"),
            "Blade Runner 2049 - The Final Cut"
        )
        # 12.12: The Day -> 12.12 - The Day (or similar)
        self.assertEqual(
            self.renamer.sanitize_for_samba("12.12: The Day"),
            "12.12 - The Day"
        )
        # Simple colon
        self.assertEqual(
            self.renamer.sanitize_for_samba("Title:Subtitle"),
            "Title-Subtitle"
        )

    def test_sanitize_slash(self):
        self.assertEqual(
            self.renamer.sanitize_for_samba("AC/DC Live"),
            "AC-DC Live"
        )
        self.assertEqual(
            self.renamer.sanitize_for_samba("AC\\DC Live"),
            "AC-DC Live"
        )

    def test_sanitize_question_mark(self):
        self.assertEqual(
            self.renamer.sanitize_for_samba("What If...?"),
            "What If..."
        )

    def test_sanitize_asterisk(self):
        self.assertEqual(
            self.renamer.sanitize_for_samba("M*A*S*H"),
            "MASH"
        )

    def test_sanitize_control_chars(self):
        # Newline, Tab
        self.assertEqual(
            self.renamer.sanitize_for_samba("Line\nBreak"),
            "LineBreak"
        )

if __name__ == "__main__":
    unittest.main()
