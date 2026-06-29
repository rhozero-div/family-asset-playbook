"""验证手册结构完整性的测试。

使用标准库 unittest,零依赖。
运行:python3 -m unittest tools.test_validate_handbook -v
"""
import re
import sys
import unittest
from pathlib import Path

# 让 unittest 能 import 同目录的 validate_handbook 模块
sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_handbook import (  # noqa: E402
    REQUIRED_FILES,
    count_h1_outside_code_fences,
    HANDBOOK_DIR as _HANDBOOK_DIR,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
HANDBOOK_DIR = REPO_ROOT / "handbook"


class TestHandbookStructure(unittest.TestCase):
    """所有手册章节的存在性、结构、版本声明校验。"""

    def test_all_required_handbook_files_exist(self):
        """所有必备手册章节都存在。"""
        missing = [f for f in REQUIRED_FILES if not (HANDBOOK_DIR / f).exists()]
        self.assertEqual(missing, [], f"缺少手册章节: {missing}")

    def test_every_handbook_file_has_exactly_one_h1(self):
        """每个手册章节都有且只有一个 H1 标题(忽略 fenced code block)。"""
        for filename in REQUIRED_FILES:
            path = HANDBOOK_DIR / filename
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8")
            h1_count = count_h1_outside_code_fences(content)
            self.assertEqual(
                h1_count, 1,
                f"{filename} 应有恰好 1 个 H1,实际 {h1_count}",
            )

    def test_every_handbook_file_has_version_block(self):
        """每个手册章节都包含版本声明。"""
        for filename in REQUIRED_FILES:
            path = HANDBOOK_DIR / filename
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8")
            self.assertRegex(
                content, r"\*\*版本:\*\*\s+\S+",
                f"{filename} 缺少版本声明",
            )

    def test_every_handbook_file_has_status_block(self):
        """每个手册章节都包含状态声明。"""
        for filename in REQUIRED_FILES:
            path = HANDBOOK_DIR / filename
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8")
            self.assertRegex(
                content, r"\*\*状态:\*\*\s+\S+",
                f"{filename} 缺少状态声明",
            )

class TestSampleClientProfile(unittest.TestCase):
    """示例客户档案的结构性校验。"""

    SAMPLE_PATH = REPO_ROOT / "samples" / "client-profile.example.yaml"

    def test_sample_yaml_exists(self):
        """示例客户档案存在。"""
        self.assertTrue(self.SAMPLE_PATH.exists(), f"缺少示例档案: {self.SAMPLE_PATH}")

    def test_sample_yaml_parses(self):
        """示例客户档案可被 YAML 解析。"""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML 未安装,跳过 YAML 解析测试")
        data = yaml.safe_load(self.SAMPLE_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)

    def test_sample_yaml_has_required_top_level_keys(self):
        """示例客户档案包含当前主链最低必要顶层字段。"""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML 未安装,跳过 YAML 解析测试")
        data = yaml.safe_load(self.SAMPLE_PATH.read_text(encoding="utf-8"))
        required = {"profile_version", "schema_version", "family", "events", "assets"}
        missing = required - set(data.keys())
        self.assertEqual(missing, set(), f"缺少维度: {missing}")

    def test_sample_yaml_profile_version(self):
        """示例档案 profile_version 字段正确。"""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML 未安装,跳过 YAML 解析测试")
        data = yaml.safe_load(self.SAMPLE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(data.get("profile_version"), "0.1")


class TestRepoLayout(unittest.TestCase):
    """仓库整体布局的校验。"""

    def test_readme_exists_and_links_to_handbook(self):
        """README 存在且链接到 handbook。"""
        readme = REPO_ROOT / "README.md"
        self.assertTrue(readme.exists(), "缺少 README.md")
        content = readme.read_text(encoding="utf-8")
        self.assertIn("handbook/", content, "README 应包含到 handbook 的链接")

class TestH1Counter(unittest.TestCase):
    """H1 计数器的单元测试(支持 fenced code block)。"""

    def test_counts_single_h1(self):
        text = "# 标题\n\n正文内容。"
        self.assertEqual(count_h1_outside_code_fences(text), 1)

    def test_ignores_h1_inside_fenced_code_block(self):
        text = "# 真实标题\n\n```\n# 这不是标题\n```\n"
        self.assertEqual(count_h1_outside_code_fences(text), 1)

    def test_ignores_h1_inside_tilde_fence(self):
        text = "# 真实标题\n\n~~~\n# 这不是标题\n~~~\n"
        self.assertEqual(count_h1_outside_code_fences(text), 1)

    def test_ignores_h1_inside_indented_code_block(self):
        text = "# 真实标题\n\n    # 缩进代码块内\n    不是 H1\n"
        self.assertEqual(count_h1_outside_code_fences(text), 1)

    def test_counts_multiple_h1_outside_fence(self):
        text = "# 第一个\n\n# 第二个\n"
        self.assertEqual(count_h1_outside_code_fences(text), 2)

    def test_handles_multiple_fences(self):
        text = "# 真实\n\n```\n# 内嵌1\n```\n\n# 第二个真实\n\n```\n# 内嵌2\n```\n"
        self.assertEqual(count_h1_outside_code_fences(text), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
