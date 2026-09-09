import os
import unittest

os.environ.setdefault("ENCRYPTION_KEY", "0123456789abcdef0123456789abcdef")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "dummy-ci-project")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("SQLITE_DB_PATH", os.path.join(os.getenv("TEMP", "/tmp"), "pipeline_demo_test.sqlite3"))
os.environ.setdefault("CHROMA_DB_DIR", os.path.join(os.getenv("TEMP", "/tmp"), "pipeline_demo_chroma_test"))

from app.services.batch_processor import (
    build_content_based_final_file_name,
    clean_generated_title,
    ensure_markdown_h1,
)


class BatchTitleHelpersTest(unittest.TestCase):
    def test_clean_generated_title_keeps_first_plain_title_line(self):
        title = clean_generated_title("# 『AI時代の雇用と成長』\n説明文です", "fallback")

        self.assertEqual(title, "AI時代の雇用と成長")

    def test_ensure_markdown_h1_replaces_existing_h1(self):
        markdown = "# 古いタイトル\n\n## はじめに\n本文です。"

        updated = ensure_markdown_h1(markdown, "新しい日本語タイトル")

        self.assertTrue(updated.startswith("# 新しい日本語タイトル\n\n"))
        self.assertNotIn("# 古いタイトル", updated)
        self.assertIn("## はじめに", updated)

    def test_ensure_markdown_h1_adds_h1_when_missing(self):
        markdown = "## はじめに\n本文です。"

        updated = ensure_markdown_h1(markdown, "内容に沿ったタイトル")

        self.assertTrue(updated.startswith("# 内容に沿ったタイトル\n\n## はじめに"))

    def test_file_name_uses_preferred_title_and_sanitizes_drive_unsafe_chars(self):
        file_name = build_content_based_final_file_name(
            "# 古いタイトル\n\n本文です。",
            "abc123ef",
            "日本/経済:AI*雇用?未来",
        )

        self.assertEqual(file_name, "日本 経済 AI雇用 未来_abc123ef.md")

    def test_file_name_fallback_does_not_duplicate_job_id(self):
        file_name = build_content_based_final_file_name("", "abc123ef", "")

        self.assertEqual(file_name, "integrated_book_abc123ef.md")


if __name__ == "__main__":
    unittest.main()
