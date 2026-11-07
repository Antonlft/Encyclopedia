#!/usr/bin/env python3
"""
update.py - keeps the capsule library in sync.

Run it from anywhere:   python3 update.py

What it does:
  1. Scans capsules/ for .html files.
  2. Adds an entry to capsules.json for every new file (fields it cannot
     guess are set to "TODO"). Existing entries are NEVER changed.
  3. Flags entries whose file no longer exists.
  4. Writes capsules-data.js so index.html works when double-clicked.
  5. Checks each capsule for common problems and prints warnings.
     It never modifies the capsule files.

Standard library only. Works with Python 3.8+.
"""

import json
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CAPSULES_DIR = ROOT / "capsules"
JSON_FILE = ROOT / "capsules.json"
JS_FILE = ROOT / "capsules-data.js"

TODO = "TODO"
FIELDS = ["title", "slug", "file", "topic", "tags", "summary",
          "date_built", "facts_verified_as_of", "status"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXTERNAL_RE = re.compile(r"^\s*(https?:)?//", re.IGNORECASE)
CSS_URL_RE = re.compile(r"""url\(\s*['"]?([^'")]+)""", re.IGNORECASE)
CSS_IMPORT_RE = re.compile(r"""@import\s+['"]([^'"]+)""", re.IGNORECASE)


# ---------------------------------------------------------------- reading pages

class PageScanner(HTMLParser):
    """Collects the title, description, viewport and any external resources."""

    # tag -> attributes that load a resource
    RESOURCE_ATTRS = {
        "script": ["src"],
        "img": ["src", "srcset"],
        "source": ["src", "srcset"],
        "video": ["src", "poster"],
        "audio": ["src"],
        "iframe": ["src"],
        "embed": ["src"],
        "object": ["data"],
        "input": ["src"],
        "image": ["href", "xlink:href"],   # SVG images
        "use": ["href", "xlink:href"],
    }
    # <link rel="..."> values that make the browser download something
    LOADING_RELS = {"stylesheet", "preload", "modulepreload", "icon",
                    "shortcut", "apple-touch-icon", "manifest", "prefetch"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = None
        self.description = None
        self.has_viewport = False
        self.external = []          # list of (what, url)
        self._in_title = False
        self._in_style = False
        self._title_parts = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title" and self.title is None:
            self._in_title = True
        elif tag == "style":
            self._in_style = True
        elif tag == "meta":
            name = a.get("name", "").lower()
            if name == "viewport":
                self.has_viewport = True
            elif name == "description" and self.description is None:
                self.description = a.get("content", "").strip() or None
        elif tag == "link":
            rels = set(a.get("rel", "").lower().split())
            if rels & self.LOADING_RELS and EXTERNAL_RE.match(a.get("href", "")):
                what = "stylesheet/font" if rels & {"stylesheet", "preload"} else "link"
                self.external.append((what, a["href"].strip()))

        for attr in self.RESOURCE_ATTRS.get(tag, []):
            value = a.get(attr, "")
            urls = [p.strip().split(" ")[0] for p in value.split(",")] if attr == "srcset" else [value]
            for url in urls:
                if EXTERNAL_RE.match(url):
                    self.external.append((tag, url.strip()))

        if "style" in a:
            self._check_css(a["style"])

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title:
            self._in_title = False
            self.title = " ".join("".join(self._title_parts).split()) or None
        elif tag == "style":
            self._in_style = False

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)
        elif self._in_style:
            self._check_css(data)

    def _check_css(self, css):
        for url in CSS_URL_RE.findall(css) + CSS_IMPORT_RE.findall(css):
            if EXTERNAL_RE.match(url):
                self.external.append(("CSS url/font", url.strip()))


def scan_page(path):
    scanner = PageScanner()
    text = path.read_text(encoding="utf-8", errors="replace")
    scanner.feed(text)
    scanner.close()
    if scanner._in_title:   # unclosed <title>
        scanner.title = " ".join("".join(scanner._title_parts).split()) or None
    return scanner


# ---------------------------------------------------------------- helpers

def rel(path):
    return path.relative_to(ROOT).as_posix()


def slugify(text):
    text = re.sub(r"[^a-z0-9]+", "-", text.lower())
    return text.strip("-") or "capsule"


def is_todo(value):
    if isinstance(value, list):
        return not value or any(is_todo(v) for v in value)
    return not str(value).strip() or str(value).strip().upper() == TODO


def load_entries():
    if not JSON_FILE.exists():
        return []
    try:
        data = json.loads(JSON_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        sys.exit(f"ERROR: capsules.json is not valid JSON (line {err.lineno}, "
                 f"column {err.colno}): {err.msg}\n"
                 "Nothing was changed. Fix the file and run again.")
    if not isinstance(data, list):
        sys.exit("ERROR: capsules.json must be a list [ ... ] of entries. Nothing was changed.")
    return data


# ---------------------------------------------------------------- main

def main():
    if not CAPSULES_DIR.is_dir():
        sys.exit(f"ERROR: folder not found: {CAPSULES_DIR}")

    entries = load_entries()
    files = sorted(p for p in CAPSULES_DIR.rglob("*")
                   if p.is_file() and p.suffix.lower() in (".html", ".htm")
                   and not any(part.startswith(".") for part in p.relative_to(CAPSULES_DIR).parts))

    # Exact-case paths of the files really in capsules/. GitHub Pages is case-sensitive,
    # so entries are matched against these strings, not with the (case-insensitive on macOS)
    # filesystem.
    scanned = {rel(p) for p in files}
    scanned_by_lower = {s.lower(): s for s in scanned}
    known_files = {e.get("file") for e in entries if isinstance(e, dict)}
    known_lower = {str(f).lower() for f in known_files if f}
    used_slugs = {e.get("slug") for e in entries if isinstance(e, dict)}
    warnings = []
    added = []

    # 1. add entries for new files (existing entries are left untouched)
    scans = {}
    for path in files:
        scans[path] = scan_page(path)
        if rel(path).lower() in known_lower:
            continue    # already listed (a case-only mismatch is reported below, not re-added)
        page = scans[path]
        slug = base = slugify(path.stem)
        n = 2
        while slug in used_slugs:
            slug = f"{base}-{n}"
            n += 1
        used_slugs.add(slug)
        entry = {
            "title": page.title or TODO,
            "slug": slug,
            "file": rel(path),
            "topic": TODO,
            "tags": [TODO],
            "summary": page.description or TODO,
            "date_built": TODO,
            "facts_verified_as_of": TODO,
            "status": "draft",
        }
        entries.append(entry)
        added.append(entry)

    if added or not JSON_FILE.exists():
        JSON_FILE.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")

    # 2. check entries (flag missing files, unfinished or malformed fields)
    flagged = []
    case_mismatches = []    # (label, real file name)
    output = []
    for i, e in enumerate(entries, 1):
        if not isinstance(e, dict):
            warnings.append(f"capsules.json entry #{i} is not an object - skipped")
            continue
        label = e.get("file") or e.get("title") or f"entry #{i}"
        item = dict(e)
        file_field = str(e.get("file") or "")
        if file_field not in scanned:
            item["_missing"] = True     # only in capsules-data.js, not in capsules.json
            real = scanned_by_lower.get(file_field.lower())
            if real:
                case_mismatches.append((label, real))
            else:
                flagged.append(label)
        for field in FIELDS:
            if field not in e:
                warnings.append(f"{label}: field '{field}' is missing")
        todos = [f for f in FIELDS if f in e and is_todo(e[f])]
        if todos:
            warnings.append(f"{label}: still TODO -> {', '.join(todos)}")
        for field in ("date_built", "facts_verified_as_of"):
            v = e.get(field)
            if v and not is_todo(v) and not DATE_RE.match(str(v)):
                warnings.append(f"{label}: {field} '{v}' should look like YYYY-MM-DD")
        if e.get("status") not in ("draft", "done"):
            warnings.append(f"{label}: status '{e.get('status')}' should be \"draft\" or \"done\"")
        if not isinstance(e.get("tags", []), list):
            warnings.append(f"{label}: tags should be a list, e.g. [\"bonds\", \"duration\"]")
        output.append(item)

    # 3. quality checks on the capsule files (read-only)
    for path in files:
        page = scans[path]
        name = rel(path)
        if not page.title:
            warnings.append(f"{name}: missing <title>")
        if not page.has_viewport:
            warnings.append(f"{name}: missing <meta name=\"viewport\"> (may look bad on phones)")
        seen = set()
        for what, url in page.external:
            if url not in seen:
                seen.add(url)
                warnings.append(f"{name}: loads {what} from the internet: {url}")

    # 4. write capsules-data.js
    JS_FILE.write_text(
        "// Generated by update.py - do not edit by hand. Edit capsules.json instead.\n"
        f"// Last updated: {date.today().isoformat()}\n"
        "window.CAPSULES = "
        + json.dumps(output, indent=2, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )

    # 5. report
    print()
    for e in added:
        print(f"  + added      {e['file']}  (status: draft - fill in the TODO fields)")
    for label in flagged:
        print(f"  ! flagged    {label}  (file not found)")
    for label, real in case_mismatches:
        print(f"  ! case       {label}  (capitals differ from the real file {real} - "
              "this link breaks on the live site; fix \"file\" in capsules.json)")
    for w in warnings:
        print(f"  - warning    {w}")
    print()
    print(f"Summary: {len(files)} capsule file(s), {len(entries)} entr{'y' if len(entries) == 1 else 'ies'} | "
          f"added {len(added)} | flagged {len(flagged)} | case mismatches {len(case_mismatches)} | "
          f"warnings {len(warnings)}")
    print(f"Wrote {rel(JS_FILE)}" + (f" and updated {rel(JSON_FILE)}" if added else ""))


if __name__ == "__main__":
    main()
