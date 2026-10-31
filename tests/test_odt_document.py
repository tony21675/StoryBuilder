import tempfile
import unittest
import zipfile
from pathlib import Path

from builder.odt_document import (
    MIMETYPE,
    markdown_to_rich_text,
    read_document,
    read_odt_document,
    save_document,
    save_odt_document,
)


class MarkdownRenderingTests(unittest.TestCase):
    def test_converts_bold_and_italic_markers_to_plain_text_ranges(self):
        plain, spans = markdown_to_rich_text(
            "A **bold phrase** and *italic words*."
        )
        self.assertEqual(plain, "A bold phrase and italic words.")
        self.assertEqual(
            spans,
            [
                (2, 13, "bold"),
                (18, 30, "italic"),
            ],
        )

    def test_converts_combined_bold_italic_markers(self):
        plain, spans = markdown_to_rich_text("This is ***important***.")
        self.assertEqual(plain, "This is important.")
        self.assertEqual(spans, [(8, 17, "bold_italic")])


class OdtDocumentTests(unittest.TestCase):
    def test_saves_a_valid_odt_with_real_emphasis_styles(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "scene.odt"
            saved = save_odt_document(
                path,
                "A **bold phrase** and *italic words*.\n\n***Both styles***.",
            )

            self.assertEqual(saved, path.resolve())
            with zipfile.ZipFile(saved) as archive:
                self.assertEqual(archive.namelist()[0], "mimetype")
                self.assertEqual(archive.read("mimetype").decode("ascii"), MIMETYPE)
                content = archive.read("content.xml").decode("utf-8")
                styles = archive.read("styles.xml").decode("utf-8")
                self.assertEqual(content.count("<text:p"), 2)
                self.assertIn('text:style-name="SB_Paragraph"', content)
                self.assertIn('style:name="SB_Paragraph"', styles)
                self.assertIn('fo:margin-bottom="0.12in"', styles)
                self.assertIn('fo:line-height="120%"', styles)
                self.assertIn("SB_Bold", content)
                self.assertIn("SB_Italic", content)
                self.assertIn("SB_BoldItalic", content)
                self.assertIn("bold phrase", content)

    def test_round_trips_bold_italic_paragraphs_and_headings(self):
        original = (
            "# Chapter Heading\n\n"
            "A **bold phrase** and *italic words*.\n\n"
            "***Both styles***."
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "scene.odt"
            save_odt_document(path, original)
            reopened = read_odt_document(path)

        self.assertEqual(reopened, original)

    def test_read_document_dispatches_odt_and_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            odt_path = root / "scene.odt"
            text_path = root / "scene.txt"
            save_document(odt_path, "A **formatted** scene.")
            save_document(text_path, "A **plain text** scene.")

            self.assertEqual(read_document(odt_path), "A **formatted** scene.")
            self.assertEqual(read_document(text_path), "A **plain text** scene.")

    def test_invalid_odt_is_reported_as_a_clear_value_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "broken.odt"
            path.write_text("not a zip file", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "valid LibreOffice ODT"):
                read_odt_document(path)

    def test_save_keeps_text_files_as_utf8_and_does_not_change_the_extension(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "draft.txt"
            saved = save_document(path, "Mañana, she said.")
            self.assertEqual(saved, path.resolve())
            self.assertEqual(path.read_text(encoding="utf-8"), "Mañana, she said.")


if __name__ == "__main__":
    unittest.main()
