"""Release verification T-X.2: Accessibility and safe HTML rendering checks."""

import ast
from pathlib import Path

UI_ROOT = Path(__file__).resolve().parents[2] / "opentrade" / "ui"


def test_no_unsafe_allow_html_with_dynamic_values_tx2() -> None:
    """T-X.2 / SECURITY T-7: UI modules must not pass dynamic values to unsafe_allow_html=True."""
    for py_file in UI_ROOT.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if (
                        kw.arg == "unsafe_allow_html"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        # Only static CSS/badge constants allowed in theme.py or badge.py
                        assert py_file.name in {
                            "theme.py",
                            "badge.py",
                        }, f"unsafe_allow_html=True found in {py_file}"


def test_every_ui_page_defines_heading_and_render_function_tx2() -> None:
    """T-X.2: Every UI page module defines a render_* function and sets a title/header."""
    pages_dir = UI_ROOT / "pages"
    for py_file in pages_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        source = py_file.read_text(encoding="utf-8")
        if len(source.splitlines()) <= 2:
            continue
        assert "def render_" in source, f"Missing render_* in {py_file.name}"
        assert ("st.title(" in source) or (
            "st.header(" in source
        ), f"Missing st.title/st.header heading in {py_file.name}"
