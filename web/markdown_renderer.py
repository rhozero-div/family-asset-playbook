"""Markdown → HTML(在剧本展示页用)。"""
import markdown as md


def render_markdown(text: str) -> str:
    """把 Markdown 文本转 HTML。

    使用标准 markdown 库,启用表格和 fenced code。
    """
    return md.markdown(
        text,
        extensions=["tables", "fenced_code"],
        output_format="html",
    )