"""Architecture and dependency rule checks per SYSTEM_ARCHITECTURE.md section 2."""

import ast
from pathlib import Path


def get_imported_modules(file_path: Path, package_root: Path) -> list[str]:
    """Parse a Python source file and return all imported module paths."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    imports: list[str] = []

    # Compute current module's dotted path relative to package root parent
    rel_path = file_path.relative_to(package_root.parent)
    parts = list(rel_path.with_suffix("").parts)
    curr_pkg = parts[:-1]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                # Relative import
                # level=1: from . import x (in current package)
                # level=2: from .. import x
                base = curr_pkg[: len(curr_pkg) - (node.level - 1)]
                if node.module:
                    full_mod = ".".join(base + node.module.split("."))
                else:
                    full_mod = ".".join(base)
                imports.append(full_mod)
            elif node.module:
                imports.append(node.module)

    return imports


def test_project_skeleton_matches_structure() -> None:
    """T0.1: Verify required files and directories from PROJECT_STRUCTURE.md exist."""
    repo_root = Path(__file__).resolve().parent.parent

    expected_paths = [
        "pyproject.toml",
        ".env.example",
        ".gitignore",
        "README.md",
        "opentrade/__init__.py",
        "opentrade/config.py",
        "opentrade/engine/__init__.py",
        "opentrade/engine/book.py",
        "opentrade/engine/flow.py",
        "opentrade/engine/impact.py",
        "opentrade/engine/hawkes.py",
        "opentrade/engine/price.py",
        "opentrade/engine/maker.py",
        "opentrade/engine/shocks.py",
        "opentrade/engine/execution.py",
        "opentrade/engine/metrics.py",
        "opentrade/engine/validation.py",
        "opentrade/engine/fast/__init__.py",
        "opentrade/services/__init__.py",
        "opentrade/services/auth.py",
        "opentrade/services/runs.py",
        "opentrade/services/catalog.py",
        "opentrade/services/market.py",
        "opentrade/services/news.py",
        "opentrade/services/analyst.py",
        "opentrade/services/chat.py",
        "opentrade/services/security.py",
        "opentrade/adapters/__init__.py",
        "opentrade/adapters/market_yfinance.py",
        "opentrade/adapters/market_twelvedata.py",
        "opentrade/adapters/news_rss.py",
        "opentrade/adapters/email_smtp.py",
        "opentrade/adapters/llm.py",
        "opentrade/storage/__init__.py",
        "opentrade/storage/db.py",
        "opentrade/storage/migrate.py",
        "opentrade/storage/repositories.py",
        "opentrade/storage/migrations/0001_init.sql",
        "opentrade/storage/migrations/0002_runs.sql",
        "opentrade/storage/migrations/0003_watchlist.sql",
        "opentrade/storage/migrations/0004_chat.sql",
        "opentrade/storage/migrations/0005_catalog.sql",
        "opentrade/storage/migrations/0006_audit.sql",
        "opentrade/ui/app.py",
        "opentrade/ui/state.py",
        "opentrade/ui/theme.py",
        "opentrade/ui/pages/home.py",
        "opentrade/ui/pages/auth_pages.py",
        "opentrade/ui/pages/tour.py",
        "opentrade/ui/pages/universe_map.py",
        "opentrade/ui/pages/simulator.py",
        "opentrade/ui/pages/impact_lab.py",
        "opentrade/ui/pages/profiles.py",
        "opentrade/ui/pages/market_data.py",
        "opentrade/ui/pages/news_lab.py",
        "opentrade/ui/pages/correlation.py",
        "opentrade/ui/pages/compare.py",
        "opentrade/ui/pages/cross_impact.py",
        "opentrade/ui/pages/execution_lab.py",
        "opentrade/ui/pages/analyst.py",
        "opentrade/ui/pages/validation.py",
        "opentrade/ui/pages/run_history.py",
        "opentrade/ui/pages/profile_account.py",
        "opentrade/ui/pages/summary.py",
        "opentrade/ui/components/badge.py",
        "opentrade/ui/components/stat_card.py",
        "opentrade/ui/components/confirm_dialog.py",
        "opentrade/ui/components/chart_container.py",
        "opentrade/ui/components/chat_panel.py",
        "opentrade/llm/guardrails.py",
        "data/catalog.csv",
        "data/presets.json",
        "data/demo/headlines.json",
        "data/demo/analyst_answers.json",
        "data/demo/chat_answers.json",
        "results/.gitkeep",
        "tests/conftest.py",
        "tests/test_architecture.py",
        "tests/engine/test_book.py",
        "tests/engine/test_flow.py",
        "tests/engine/test_impact.py",
        "tests/engine/test_metrics.py",
        "tests/services/test_auth.py",
        "tests/services/test_runs.py",
        "tests/services/test_catalog.py",
        "tests/services/test_analyst.py",
        "tests/services/test_chat.py",
        "tests/storage/test_migrations.py",
        "tests/ui/test_provenance_labels.py",
        "tests/ui/test_browser_flows.py",
    ]

    missing = [rel for rel in expected_paths if not (repo_root / rel).exists()]
    assert not missing, f"Missing paths from PROJECT_STRUCTURE.md: {missing}"


def test_layer_dependency_rules_pass() -> None:
    """T0.1: Verify import rules per SYSTEM_ARCHITECTURE.md section 2.

    Rules:
    - UI may import services. It never imports storage, adapters, or engine internals directly.
      It may import engine result types for display only.
    - Services may import engine, storage, and adapters.
    - Engine imports only Python standard library and numpy (if needed).
      No UI, no storage, no adapters.
    - Adapters import no internal modules except config.
    - Storage imports no service or UI modules.
    """
    repo_root = Path(__file__).resolve().parent.parent
    package_root = repo_root / "opentrade"

    assert package_root.exists(), "opentrade package directory does not exist"

    violations: list[str] = []

    for py_file in package_root.rglob("*.py"):
        rel_to_pkg = py_file.relative_to(package_root)
        layer = rel_to_pkg.parts[0] if len(rel_to_pkg.parts) > 1 else ""

        imports = get_imported_modules(py_file, package_root)

        for imp in imports:
            # Check engine layer
            if layer == "engine" and imp.startswith(
                (
                    "opentrade.ui",
                    "opentrade.services",
                    "opentrade.adapters",
                    "opentrade.storage",
                )
            ):
                violations.append(f"{py_file}: engine must not import {imp}")

            # Check ui layer
            elif layer == "ui":
                # UI never imports storage or adapters or engine internals directly
                if imp.startswith(("opentrade.storage", "opentrade.adapters")):
                    violations.append(f"{py_file}: ui must not import {imp}")
                if imp.startswith("opentrade.engine") and not imp.startswith(
                    ("opentrade.engine.results", "opentrade.engine.types")
                ):
                    violations.append(f"{py_file}: ui must not import engine internals ({imp})")

            # Check adapters layer
            elif (
                layer == "adapters"
                and imp.startswith("opentrade.")
                and not imp.startswith(("opentrade.config", "opentrade.adapters"))
            ):
                violations.append(f"{py_file}: adapters must not import internal module {imp}")

            # Check storage layer
            elif layer == "storage" and imp.startswith(("opentrade.services", "opentrade.ui")):
                violations.append(f"{py_file}: storage must not import {imp}")

    assert not violations, "Layer dependency violations found:\n" + "\n".join(violations)
