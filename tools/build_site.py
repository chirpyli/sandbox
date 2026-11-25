#!/usr/bin/env python3
"""Build docs/ from content/**/*.md for GitHub Pages.

Usage:
    python3 tools/build_site.py
    python3 tools/build_site.py --write-meta
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import markdown
import yaml
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIR = ROOT / "content"
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "docs"
ARTICLE_DIR = OUTPUT_DIR / "articles"
ASSET_DIR = OUTPUT_DIR / "assets"
CONTENT_ASSET_DIR = ASSET_DIR / "content"

SITE_TITLE = "AI 智能体沙箱"
REPO_URL = "https://github.com/chirpyli/sandbox"
SITE_URL = "https://chirpyli.github.io/sandbox/"
PREFIX = "../../"

CATEGORY_LABELS = {
    "overview": "总览",
    "agent-sandbox": "Agent Sandbox",
    "kata": "Kata Containers",
    "vm": "虚拟化",
    "cubesandbox": "CubeSandbox",
    "opensandbox": "OpenSandbox",
    "substrate": "Substrate",
}
CATEGORY_ORDER = [
    "overview",
    "agent-sandbox",
    "kata",
    "vm",
    "cubesandbox",
    "opensandbox",
    "substrate",
]

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
HEADING_RE = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", re.M)
LINK_RE = re.compile(r"(\]\()([^)\s]+)(\))")
MERMAID_RE = re.compile(r'<pre><code class="language-mermaid">(.*?)</code></pre>', re.S)
PLACEHOLDER_RE = re.compile(r"%%([A-Z_]+)%%")


def slugify_heading(value: str, separator: str) -> str:
    slug = re.sub(r"[^\w]+", separator, value.lower()).strip(separator)
    return slug or "section"


class ListSpacingPreprocessor(Preprocessor):
    """让紧接正文的列表无需空行也能被解析。"""

    def run(self, lines: list[str]) -> list[str]:
        result: list[str] = []
        in_fence = False
        for line in lines:
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
            previous = result[-1] if result else ""
            needs_gap = (
                not in_fence
                and bool(previous.strip())
                and bool(re.match(r"^[ \t]*[-*+][ \t]+\S", line))
                and not re.match(r"^[ \t]*(?:[-*+][ \t]+|\d+\.[ \t]+|>|#|\||```)", previous)
            )
            if needs_gap:
                result.append("")
            result.append(line)
        return result


class SandboxMarkdownExtension(Extension):
    def extendMarkdown(self, md) -> None:
        md.preprocessors.register(ListSpacingPreprocessor(md), "list-spacing", 90)


@dataclass
class Document:
    path: Path
    slug: str
    title: str
    description: str
    category: str
    category_label: str
    order: int
    lang: str
    tags: list[str]
    meta: dict
    raw_body: str
    body: str


def split_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    for index in range(1, len(lines)):
        if lines[index].strip() != "---":
            continue
        raw = "".join(lines[1:index]).strip()
        meta = yaml.safe_load(raw) if raw else {}
        if meta is None:
            meta = {}
        if not isinstance(meta, dict):
            raise ValueError("frontmatter 必须是 YAML 映射")
        return meta, "".join(lines[index + 1 :])
    raise ValueError("frontmatter 缺少结束的 ---")


def slugify(value: str) -> str:
    value = value.lower().replace("_", "-")
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def extract_title(body: str, fallback: str) -> tuple[str, str]:
    match = HEADING_RE.search(body)
    if not match or body[: match.start()].strip():
        return fallback, body
    end = match.end()
    while end < len(body) and body[end] == "\n":
        end += 1
    return match.group(2).strip(), body[: match.start()] + body[end:]


def extract_description(body: str) -> str:
    paragraph: list[str] = []
    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not stripped:
            if paragraph:
                break
            continue
        if stripped.startswith(("#", ">", "- ", "* ", "|", "![", "```")):
            if paragraph:
                break
            continue
        paragraph.append(stripped)
    text = " ".join(paragraph)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*`_]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120] + ("…" if len(text) > 120 else "")


def load_documents() -> list[Document]:
    documents: list[Document] = []
    for path in sorted(CONTENT_DIR.rglob("*.md")):
        relative = path.relative_to(CONTENT_DIR)
        if "assets" in relative.parts:
            continue
        meta, raw_body = split_frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("draft"):
            continue

        parent = relative.parts[0] if len(relative.parts) > 1 else "overview"
        category = str(meta.get("category") or parent)
        fallback_title = path.stem.replace("-", " ").replace("_", " ")
        title, body = extract_title(raw_body, fallback_title)
        title = str(meta.get("title") or title)
        slug = str(meta.get("slug") or slugify(path.stem))
        if not SLUG_RE.fullmatch(slug):
            raise ValueError(
                f"{path}: 无效 slug {slug!r}，请使用小写英文与连字符，或在 frontmatter 中显式指定 slug"
            )

        tags = meta.get("tags") or []
        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        elif not isinstance(tags, list):
            tags = []

        try:
            order = int(meta.get("order", 100))
        except (TypeError, ValueError):
            order = 100

        documents.append(
            Document(
                path=path,
                slug=slug,
                title=title,
                description=str(meta.get("description") or extract_description(body)),
                category=category,
                category_label=CATEGORY_LABELS.get(
                    category, category.replace("-", " ").title()
                ),
                order=order,
                lang=str(meta.get("lang") or "zh"),
                tags=[str(tag) for tag in tags],
                meta=meta,
                raw_body=raw_body,
                body=body,
            )
        )

    slugs = [doc.slug for doc in documents]
    duplicates = {slug for slug in slugs if slugs.count(slug) > 1}
    if duplicates:
        raise ValueError(f"slug 重复：{', '.join(sorted(duplicates))}")

    documents.sort(
        key=lambda doc: (
            CATEGORY_ORDER.index(doc.category)
            if doc.category in CATEGORY_ORDER
            else len(CATEGORY_ORDER),
            doc.order,
            doc.title,
        )
    )
    return documents


def write_frontmatter(documents: list[Document]) -> None:
    for doc in documents:
        data = {
            "title": doc.title,
            "slug": doc.slug,
            "description": doc.description,
            "category": doc.category,
            "order": doc.order,
            "lang": doc.lang,
            "draft": bool(doc.meta.get("draft", False)),
        }
        if doc.tags:
            data["tags"] = doc.tags
        for key, value in doc.meta.items():
            if key not in data:
                data[key] = value
        frontmatter = yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=4096,
        ).strip()
        doc.path.write_text(
            f"---\n{frontmatter}\n---\n\n{doc.raw_body.lstrip()}", encoding="utf-8"
        )


def rewrite_links(body: str, source: Path, slug_by_path: dict[Path, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        url = match.group(2)
        if url.startswith(("http://", "https://", "mailto:", "#", "data:")):
            return match.group(0)
        path_part, separator, anchor = url.partition("#")
        if not path_part:
            return match.group(0)

        if "assets/" in path_part and not path_part.startswith(("http:", "https:")):
            rest = path_part.split("assets/", 1)[1]
            target = f"{PREFIX}assets/content/{rest}"
        elif path_part.endswith(".md"):
            resolved = (source.parent / path_part).resolve()
            slug = slug_by_path.get(resolved)
            if not slug:
                return match.group(0)
            target = f"../{slug}/"
        else:
            return match.group(0)

        if separator:
            target += f"#{anchor}"
        return f"{match.group(1)}{target}{match.group(3)}"

    return LINK_RE.sub(replace, body)


def render_markdown(body: str) -> tuple[str, str]:
    converter = markdown.Markdown(
        extensions=["extra", "admonition", "toc", "sane_lists", SandboxMarkdownExtension()],
        extension_configs={
            "toc": {"toc_depth": "2-3", "slugify": slugify_heading},
        },
    )
    content = converter.convert(body)
    content = MERMAID_RE.sub(
        lambda match: f'<div class="mermaid">{html.unescape(match.group(1))}</div>',
        content,
    )
    return content, converter.toc


def fill_template(template: str, values: dict[str, str]) -> str:
    return PLACEHOLDER_RE.sub(
        lambda match: values.get(match.group(1), match.group(0)), template
    )


def navigation_link(doc: Optional[Document], label: str) -> str:
    if doc is None:
        return ""
    return (
        '<a class="page-nav-link" href="../'
        f'{doc.slug}/"><span>{label}</span><strong>{html.escape(doc.title)}</strong></a>'
    )


def render_articles(
    documents: list[Document], template: str, slug_by_path: dict[Path, str]
) -> None:
    for index, doc in enumerate(documents):
        body_html, toc = render_markdown(
            rewrite_links(doc.body, doc.path, slug_by_path)
        )
        tags = "".join(
            f'<span class="tag">{html.escape(tag)}</span>' for tag in doc.tags
        )
        previous = documents[index - 1] if index > 0 else None
        following = documents[index + 1] if index + 1 < len(documents) else None
        values = {
            "PREFIX": PREFIX,
            "SITE_TITLE": html.escape(SITE_TITLE),
            "REPO_URL": html.escape(REPO_URL),
            "TITLE": html.escape(doc.title),
            "DESCRIPTION": html.escape(doc.description),
            "CATEGORY": html.escape(doc.category_label),
            "LANG": html.escape(doc.lang.upper()),
            "TAGS": tags,
            "TOC": toc,
            "BODY": body_html,
            "PREV": navigation_link(previous, "上一篇"),
            "NEXT": navigation_link(following, "下一篇"),
            "YEAR": str(datetime.now().year),
        }
        target = ARTICLE_DIR / doc.slug / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(fill_template(template, values), encoding="utf-8")


def render_home(documents: list[Document], template: str) -> None:
    grouped: dict[str, list[Document]] = {}
    for doc in documents:
        grouped.setdefault(doc.category, []).append(doc)

    def category_key(category: str) -> tuple[int, str]:
        if category in CATEGORY_ORDER:
            return CATEGORY_ORDER.index(category), ""
        return len(CATEGORY_ORDER), category

    sections: list[str] = []
    for category in sorted(grouped, key=category_key):
        cards: list[str] = []
        for doc in grouped[category]:
            cards.append(
                '<article class="article-card">\n'
                f'          <a class="card-link" href="articles/{doc.slug}/">{html.escape(doc.title)}</a>\n'
                f'          <p class="card-desc">{html.escape(doc.description)}</p>\n'
                f'          <div class="card-meta"><span>{html.escape(doc.lang.upper())}</span><code>{html.escape(doc.slug)}</code></div>\n'
                "        </article>"
            )
        label = html.escape(grouped[category][0].category_label)
        anchor = html.escape(category)
        sections.append(
            f'<section class="section" id="{anchor}">\n'
            '      <div class="section-head">\n'
            f"        <h2>{label}</h2>\n"
            f'        <span class="count">{len(grouped[category])} 篇</span>\n'
            "      </div>\n"
            '      <div class="article-grid">\n'
            + "\n".join(f"        {card}" for card in cards)
            + "\n      </div>\n"
            "    </section>"
        )

    values = {
        "SITE_TITLE": html.escape(SITE_TITLE),
        "REPO_URL": html.escape(REPO_URL),
        "SITE_URL": html.escape(SITE_URL),
        "ARTICLE_COUNT": str(len(documents)),
        "CATEGORY_COUNT": str(len(grouped)),
        "SECTIONS": "\n    ".join(sections),
        "YEAR": str(datetime.now().year),
    }
    (OUTPUT_DIR / "index.html").write_text(
        fill_template(template, values), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 AI 智能体沙箱静态站点")
    parser.add_argument(
        "--write-meta",
        action="store_true",
        help="把自动生成的 frontmatter 写回 content 目录下的 Markdown 源文件",
    )
    args = parser.parse_args()

    documents = load_documents()
    if args.write_meta:
        write_frontmatter(documents)

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLE_DIR.mkdir(parents=True, exist_ok=True)

    shutil.copy2(TEMPLATE_DIR / "style.css", ASSET_DIR / "style.css")
    shutil.copy2(TEMPLATE_DIR / "favicon.svg", ASSET_DIR / "favicon.svg")
    asset_source = CONTENT_DIR / "assets"
    if asset_source.is_dir():
        shutil.copytree(asset_source, CONTENT_ASSET_DIR, dirs_exist_ok=True)

    slug_by_path = {doc.path.resolve(): doc.slug for doc in documents}
    render_articles(
        documents,
        (TEMPLATE_DIR / "article.html").read_text(encoding="utf-8"),
        slug_by_path,
    )
    render_home(documents, (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8"))
    (OUTPUT_DIR / ".nojekyll").touch()

    print(
        f"Generated {len(documents)} articles in {len({doc.category for doc in documents})} "
        f"categories -> {OUTPUT_DIR}"
    )


if __name__ == "__main__":
    main()
