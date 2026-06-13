from pathlib import Path

DOCS_DIR = Path("docs")
TEMPLATE_PATH = DOCS_DIR / "README-template.md"
README_PATH = DOCS_DIR / "README.md"

DOCS_LIST_PLACEHOLDER = "{{ DOCS_LIST }}"

EXCLUDED_FILES = {"README.md", "README-template.md"}


def extract_title(path: Path) -> str:
    """Return the first top-level markdown title from a document."""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped.removeprefix("# ").strip()

    return path.stem


def collect_docs() -> list[Path]:
    """Collect markdown documents that should appear in docs/README.md."""
    return sorted(
        path
        for path in DOCS_DIR.glob("*.md")
        if path.name not in EXCLUDED_FILES
    )


def build_docs_list() -> str:
    """Build the markdown document list from docs/*.md files."""
    rows = []

    for path in collect_docs():
        title = extract_title(path)
        rows.append(f"* `{path.name}`: {title}")

    return "\n".join(rows)


def render_readme(template_text: str) -> str:
    """Render docs/README.md from docs/README-template.md."""
    if DOCS_LIST_PLACEHOLDER not in template_text:
        raise ValueError(
            f"{TEMPLATE_PATH} 파일에 {DOCS_LIST_PLACEHOLDER} placeholder가 없습니다."
        )

    return template_text.replace(DOCS_LIST_PLACEHOLDER, build_docs_list())


def update_readme() -> None:
    """Generate docs/README.md from docs/README-template.md."""
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"{TEMPLATE_PATH} 파일을 찾을 수 없습니다.")

    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    updated_text = render_readme(template_text)

    README_PATH.write_text(updated_text, encoding="utf-8")


if __name__ == "__main__":
    update_readme()
    print(f"Updated {README_PATH} from {TEMPLATE_PATH}")