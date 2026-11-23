import os
import unittest
from pathlib import Path

from builder.workspace import LLAMA, MODELS_DIR, NOVEL_ROOT, WORKSPACE_ROOT


class DocumentsWorkspaceDefaultsTests(unittest.TestCase):
    def test_default_workspace_is_documents_not_the_checkout_parent(self):
        if "STORY_WORKSPACE_ROOT" in os.environ:
            self.skipTest("STORY_WORKSPACE_ROOT explicitly overrides the default")
        documents = (Path.home() / "Documents").resolve()
        self.assertEqual(WORKSPACE_ROOT, documents)

    def test_default_models_novels_and_llama_paths_are_under_documents(self):
        if any(key in os.environ for key in (
            "STORY_WORKSPACE_ROOT", "STORY_MODELS_DIR",
            "STORY_NOVEL_ROOT", "STORY_LLAMA_PATH",
        )):
            self.skipTest("A workspace/resource environment variable explicitly overrides a default")
        documents = (Path.home() / "Documents").resolve()
        self.assertEqual(MODELS_DIR, documents / "Models")
        self.assertEqual(NOVEL_ROOT, documents / "MyNovel")
        self.assertEqual(LLAMA, documents / "llama.cpp" / "build" / "bin" / "llama-cli")


if __name__ == "__main__":
    unittest.main()
