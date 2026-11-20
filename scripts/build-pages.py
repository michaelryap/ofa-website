#!/usr/bin/env python3
"""Builds the site's HTML pages from a snapshot of the "OFA Website Copy" Google Doc.

Usage: python3 scripts/build-pages.py

Reads content/copy.json (the doc, as the Google Docs API returns it) and
content/media.json (alt text and sizes for images and videos), and rewrites
one HTML page per page in the doc. The rules follow the doc's README:

- A Heading 1 starts a page. "[Home]" in brackets is a label and isn't shown;
  "Pussypedia" without brackets is shown as the page's <h1>.
- A Heading 2 starts a section. In brackets it's a label; without, an <h2>.
- Other headings without brackets keep their level. Headings in brackets,
  paragraphs that are entirely italic (prompts for the writer) and horizontal
  lines are skipped.
- Bold, italics and links carry over. Footnotes become numbered notes at the
  end of each page.
- A bulleted list where each item has exactly one indented item under it is a
  list of labels and values, and becomes a <dl>.
- A paragraph in quotation marks followed by a line starting with an em dash
  is a quote and its source.
- "[image: file.jpg]" or "[video: file.mp4]" on its own line places a file
  from assets/images/<page>/ or assets/videos/<page>/.
- Heading 3s in Work > [Projects] become links to each project's page.
"""

import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE_NAME = "Our Future Agency"
NAV = [("Work", "work.html"), ("About", "about.html"), ("Contact", "contact.html")]
GENERATED_NOTE = "<!-- Generated from the OFA Website Copy Google Doc by scripts/build-pages.py. Edit the doc, not this file. -->"

warnings = []


def warn(message):
    warnings.append(message)


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower().replace("&", "")).strip("-")


def is_label(text):
    return text.startswith("[") and text.endswith("]")


def unlabel(text):
    return text[1:-1].strip() if is_label(text) else text


def page_filename(name):
    return "index.html" if name == "Home" else f"{slugify(name)}.html"


# Reading the doc


def load_document(path):
    data = json.loads(path.read_text())
    if "content" in data and "tabs" not in data:
        data = data["content"]
    if "tabs" in data:
        data = data["tabs"][0]["documentTab"]
    return data


def clean(text):
    # Soft line breaks (Shift+Enter) inside a paragraph become <br>; the
    # newline that ends every paragraph is dropped
    return text.replace("\n", "").replace(" ", "\u000b")


class Paragraph:
    def __init__(self, paragraph, lists):
        self.style = paragraph["paragraphStyle"].get("namedStyleType", "NORMAL_TEXT")
        self.runs = []  # (text, bold, italic, link) or ("footnote", id)
        for element in paragraph["elements"]:
            if "textRun" in element:
                run = element["textRun"]
                style = run.get("textStyle", {})
                text = clean(run["content"])
                if text:
                    self.runs.append((text, bool(style.get("bold")), bool(style.get("italic")),
                                      style.get("link", {}).get("url")))
            elif "footnoteReference" in element:
                self.runs.append(("footnote", element["footnoteReference"]["footnoteId"]))
        self.bullet_level = None
        self.numbered = False
        if "bullet" in paragraph:
            self.bullet_level = paragraph["bullet"].get("nestingLevel", 0)
            levels = lists.get(paragraph["bullet"]["listId"], {}).get("listProperties", {}).get("nestingLevels", [])
            if self.bullet_level < len(levels):
                glyph = levels[self.bullet_level].get("glyphType")
                self.numbered = glyph not in (None, "GLYPH_TYPE_UNSPECIFIED", "NONE")

    @property
    def text(self):
        return "".join(r[0] for r in self.runs if r[0] != "footnote").replace("\u000b", " ").strip()

    @property
    def is_prompt(self):
        # Entirely italic, so it's a note to the writer rather than copy
        text_runs = [r for r in self.runs if r[0] != "footnote" and r[0].strip()]
        return bool(text_runs) and all(r[2] for r in text_runs)

    @property
    def heading_level(self):
        match = re.fullmatch(r"HEADING_([1-6])", self.style)
        return int(match.group(1)) if match else None


def read_paragraphs(document):
    lists = document.get("lists", {})
    for element in document["body"]["content"]:
        if "paragraph" in element:
            yield Paragraph(element["paragraph"], lists)


# Inline formatting


class Footnotes:
    """Numbers footnotes per page, in the order they appear."""

    def __init__(self, document):
        self.document = document
        self.order = []

    def reference(self, footnote_id):
        self.order.append(footnote_id)
        n = len(self.order)
        return f'<sup><a href="#note-{n}" id="ref-{n}">{n}</a></sup>'

    def content(self, footnote_id):
        footnote = self.document.get("footnotes", {}).get(footnote_id)
        if not footnote:
            return ""
        lists = self.document.get("lists", {})
        paragraphs = [Paragraph(e["paragraph"], lists) for e in footnote["content"] if "paragraph" in e]
        return " ".join(inline(p.runs, None) for p in paragraphs).strip()


def inline(runs, footnotes):
    # Merge neighbouring runs with the same formatting so a link isn't split
    # into several <a> tags
    merged = []
    for run in runs:
        if run[0] != "footnote" and merged and merged[-1][0] != "footnote" and merged[-1][1:] == run[1:]:
            merged[-1] = (merged[-1][0] + run[0],) + run[1:]
        else:
            merged.append(run)

    out = []
    for run in merged:
        if run[0] == "footnote":
            if footnotes:
                out.append(footnotes.reference(run[1]))
            continue
        text, bold, italic, link = run
        piece = html.escape(text, quote=False).replace("\u000b", "<br>")
        if italic:
            piece = f"<em>{piece}</em>"
        if bold:
            piece = f"<strong>{piece}</strong>"
        if link:
            piece = f'<a href="{html.escape(link)}">{piece}</a>'
        out.append(piece)
    result = "".join(out)
    # Trim spaces at the ends, including inside the first and last tags
    result = re.sub(r"^((?:<[^>]+>)*)\s+", r"\1", result)
    result = re.sub(r"\s+((?:</[^>]+>|<sup>.*?</sup>)*)$", r"\1", result)
    result = re.sub(r"(<br>)+((?:</[^>]+>)*)$", r"\2", result)
    return result


# Building pages


class Page:
    def __init__(self, name, heading):
        self.name = name
        self.heading = heading  # shown <h1>, or None when the page only has a label
        self.slug = slugify(name)
        self.filename = page_filename(name)
        self.blocks = []  # paragraphs before the first section
        self.sections = []  # (label or heading text, is_label, [paragraphs])

    def add(self, paragraph):
        (self.sections[-1][2] if self.sections else self.blocks).append(paragraph)


def split_pages(paragraphs):
    pages = []
    skipping = False
    for p in paragraphs:
        level = p.heading_level
        text = p.text
        if level == 1 and text:
            skipping = text == "[README]"
            if not skipping:
                pages.append(Page(unlabel(text), None if is_label(text) else text))
            continue
        if skipping or not pages:
            continue
        if level == 2 and text:
            pages[-1].sections.append((unlabel(text), is_label(text), []))
            continue
        pages[-1].add(p)
    return pages


MARKER = re.compile(r"\[(image|video):\s*([^\]]+?)\s*\]")


def render_media(kind, filename, page, media, indent):
    key = f"{page.slug}/{filename}"
    info = media.get(key)
    if info is None:
        warn(f"No alt text or size in content/media.json for {key}")
        info = {}
    folder = "images" if kind == "image" else "videos"
    src = f"assets/{folder}/{page.slug}/{filename}"
    if not (ROOT / src).exists():
        warn(f"Missing file {src}, placed by [{kind}: {filename}] on the {page.name} page")
    size = ""
    if "width" in info and "height" in info:
        size = f' width="{info["width"]}" height="{info["height"]}"'
    alt = html.escape(info.get("alt", ""))
    if kind == "image":
        return [f'{indent}<img src="{src}" alt="{alt}"{size}>']
    fallback = html.escape(info.get("fallback", "Watch the video"), quote=False)
    return [
        f'{indent}<video src="{src}"{size} autoplay muted loop playsinline controls aria-label="{alt}">',
        f'{indent}  <a href="{src}">{fallback}</a>',
        f"{indent}</video>",
    ]


def render_list(items, footnotes, indent):
    # Label/value pairs: every top-level item has exactly one indented item
    pairs = []
    i = 0
    while i < len(items):
        if (items[i].bullet_level == 0 and i + 1 < len(items) and items[i + 1].bullet_level == 1
                and (i + 2 >= len(items) or items[i + 2].bullet_level == 0)):
            pairs.append((items[i], items[i + 1]))
            i += 2
        else:
            pairs = None
            break
    if pairs:
        lines = [f"{indent}<dl>"]
        for label, value in pairs:
            lines += [f"{indent}  <div>",
                      f"{indent}    <dt>{inline(label.runs, footnotes)}</dt>",
                      f"{indent}    <dd>{inline(value.runs, footnotes)}</dd>",
                      f"{indent}  </div>"]
        return lines + [f"{indent}</dl>"]

    # Ordinary list; indented items become a list inside the item above them
    def nested(items, level, indent):
        tag = "ol" if items[0].numbered else "ul"
        lines = [f"{indent}<{tag}>"]
        i = 0
        while i < len(items):
            item = items[i]
            children = []
            i += 1
            while i < len(items) and items[i].bullet_level > level:
                children.append(items[i])
                i += 1
            if children:
                lines.append(f"{indent}  <li>{inline(item.runs, footnotes)}")
                lines += nested(children, level + 1, indent + "    ")
                lines.append(f"{indent}  </li>")
            else:
                lines.append(f"{indent}  <li>{inline(item.runs, footnotes)}</li>")
        return lines + [f"{indent}</{tag}>"]

    return nested(items, 0, indent)


def render_blocks(paragraphs, page, footnotes, media, indent, projects=None):
    lines = []
    i = 0
    while i < len(paragraphs):
        p = paragraphs[i]
        text = p.text
        level = p.heading_level

        if p.bullet_level is not None:
            items = []
            while i < len(paragraphs) and paragraphs[i].bullet_level is not None:
                if not paragraphs[i].is_prompt and paragraphs[i].text:
                    items.append(paragraphs[i])
                i += 1
            if items:
                lines += render_list(items, footnotes, indent)
            continue

        i += 1
        if not text or p.is_prompt:
            continue

        if level:
            if is_label(text):
                continue
            if projects is not None and level == 3:
                projects.append(text)
                continue
            lines.append(f"{indent}<h{level}>{inline(p.runs, footnotes)}</h{level}>")
            continue

        marker = MARKER.fullmatch(text)
        if marker:
            lines += render_media(marker.group(1), marker.group(2), page, media, indent)
            continue
        if is_label(text):
            warn(f"Skipped [{unlabel(text)}] on the {page.name} page: not an image or video marker")
            continue

        # A quote: in quotation marks, followed by its source after an em dash
        following = paragraphs[i] if i < len(paragraphs) else None
        if (text[0] in "“\"" and following is not None and following.heading_level is None
                and following.text.startswith("—")):
            source_link = next((r[3] for r in following.runs if r[0] != "footnote" and r[3]), None)
            cite = f' cite="{html.escape(source_link)}"' if source_link else ""
            lines += [f'{indent}<figure class="quote">',
                      f"{indent}  <blockquote{cite}>",
                      f"{indent}    <p>{inline(p.runs, footnotes)}</p>",
                      f"{indent}  </blockquote>",
                      f"{indent}  <figcaption>{inline(following.runs, footnotes)}</figcaption>",
                      f"{indent}</figure>"]
            i += 1
            continue

        lines.append(f"{indent}<p>{inline(p.runs, footnotes)}</p>")

    if projects:
        lines.append(f"{indent}<ul>")
        for name in projects:
            lines.append(f'{indent}  <li><a href="{page_filename(name)}">{html.escape(name, quote=False)}</a></li>')
        lines.append(f"{indent}</ul>")
    return lines


def render_page(page, document, media):
    footnotes = Footnotes(document)
    title = SITE_NAME if page.name == "Home" else f"{page.name} · {SITE_NAME}"

    main = []
    if page.heading:
        h1 = f"<h1>{html.escape(page.heading, quote=False)}</h1>"
    elif page.name == "Home":
        h1 = f'<h1 class="visually-hidden">{SITE_NAME}</h1>'
    else:
        h1 = f"<h1>{html.escape(page.name, quote=False)}</h1>"
    main += ["    <section>", f"      {h1}", "    </section>"]

    lead = render_blocks(page.blocks, page, footnotes, media, "    ")
    if lead:
        main += [""] + lead

    for name, labelled, paragraphs in page.sections:
        projects = [] if (page.name == "Work" and labelled and name == "Projects") else None
        body = render_blocks(paragraphs, page, footnotes, media, "      ", projects)
        if not body:
            continue  # nothing written yet, only prompts
        heading = [] if labelled else [f"      <h2>{html.escape(name, quote=False)}</h2>"]
        main += ["", f'    <section class="{slugify(name)}">'] + heading + body + ["    </section>"]

    if footnotes.order:
        main += ["", '    <section class="notes" aria-label="Notes">', "      <ol>"]
        for n, footnote_id in enumerate(footnotes.order, 1):
            main.append(f'        <li id="note-{n}">{footnotes.content(footnote_id)} '
                        f'<a href="#ref-{n}" aria-label="Back to text">↩</a></li>')
        main += ["      </ol>", "    </section>"]

    nav = []
    for label, href in NAV:
        current = ' aria-current="page"' if href == page.filename else ""
        nav.append(f'        <li><a href="{href}"{current}>{label}</a></li>')

    return "\n".join([
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"  <title>{html.escape(title, quote=False)}</title>",
        '  <link rel="stylesheet" href="styles.css">',
        "</head>",
        "<body>",
        GENERATED_NOTE,
        "",
        "  <header>",
        '    <a href="index.html">OFA</a>',
        '    <nav aria-label="Main">',
        "      <ul>",
        *nav,
        "      </ul>",
        "    </nav>",
        "  </header>",
        "",
        "  <main>",
        *main,
        "  </main>",
        "",
        "</body>",
        "</html>",
        "",
    ])


def main():
    document = load_document(ROOT / "content" / "copy.json")
    media = json.loads((ROOT / "content" / "media.json").read_text())
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT

    for page in split_pages(read_paragraphs(document)):
        path = out_dir / page.filename
        path.write_text(render_page(page, document, media))
        print(f"Wrote {path.relative_to(out_dir) if out_dir == ROOT else path}")

    # On GitHub, "::warning::" shows the message as an alert on the Actions run
    prefix = "::warning::" if os.environ.get("GITHUB_ACTIONS") else "Warning: "
    for message in warnings:
        print(f"{prefix}{message}", file=sys.stderr)


if __name__ == "__main__":
    main()
