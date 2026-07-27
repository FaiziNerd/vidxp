import unittest
from pathlib import Path

from vidxp.capabilities.registry import CAPABILITIES


ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_capability_extras_read_capability_owned_requirements(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        all_block = pyproject.split("all = { file = [", 1)[1].split(
            "] }",
            1,
        )[0]

        for capability in CAPABILITIES.values():
            requirements = (
                ROOT
                / "src"
                / "vidxp"
                / "capabilities"
                / capability.name
                / "requirements.txt"
            )
            relative = requirements.relative_to(ROOT).as_posix()
            self.assertTrue(requirements.is_file())
            self.assertIn(
                f'{capability.extra} = {{ file = ["{relative}"] }}',
                pyproject,
            )
            self.assertIn(f'"{relative}"', all_block)

        self.assertNotIn("benchmarks/requirements.txt", all_block)
        self.assertNotIn("requirements/frontend.txt", all_block)

    def test_base_dependencies_exclude_capability_runtimes(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        base_dependencies = pyproject.split("dependencies = [", 1)[1].split(
            "]",
            1,
        )[0]

        for distribution in (
            "chromadb",
            "face-recognition",
            "moviepy",
            "numpy",
            "opencv-python",
            "sentence-transformers",
            "torch",
            "whisperx",
            "clip-anytorch",
            "streamlit",
            "srt",
        ):
            self.assertNotIn(distribution, base_dependencies)


if __name__ == "__main__":
    unittest.main()
