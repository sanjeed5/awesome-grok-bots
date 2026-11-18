#!/usr/bin/env python3
"""Refresh the official x.ai Grok Bot marketplace index.

Reads the public catalog at https://x.ai/bot/marketplace (the Next.js RSC
payload the page itself ships). Optionally enriches each template from the
public GetPublicGrokBotMarketplaceListing endpoint. Writes
data/marketplace.json and marketplace/README.md.

This script only uses public pages and public endpoints. It never stores
pre-signed recipe download URLs.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MARKETPLACE_URL = "https://x.ai/bot/marketplace"
LISTING_URL = (
    "https://api2.cursor.sh/aiserver.v1.GrokBotService/"
    "GetPublicGrokBotMarketplaceListing"
)
USER_AGENT = (
    "awesome-grok-bots/1.0 (+https://github.com/sanjeed5/awesome-grok-bots) "
    "Mozilla/5.0"
)
# Official category pages, in the order the marketplace uses.
CATEGORY_PAGES = [
    ("From Grok Bot Team", "from-grok-bot-team"),
    ("Engineering", "engineering"),
    ("Sales", "sales"),
    ("Marketing", "marketing"),
    ("Design", "design"),
    ("Personal", "personal"),
    ("Recruiting & People", "recruiting-people"),
    ("Product", "product"),
    ("Operations", "operations"),
]
REPO_ROOT = Path(__file__).resolve().parent.parent


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def request(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str | None = None,
    timeout: int = 30,
) -> tuple[int, dict[str, str], bytes]:
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return exc.code, dict(exc.headers or {}), body


def unescape_js_string(s: str) -> str:
    """Decode a JS double-quoted string body, leaving UTF-8 characters intact."""
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        if i + 1 >= n:
            break
        nxt = s[i + 1]
        if nxt == "n":
            out.append("\n")
            i += 2
        elif nxt == "r":
            out.append("\r")
            i += 2
        elif nxt == "t":
            out.append("\t")
            i += 2
        elif nxt in "\"'\\/":
            out.append(nxt)
            i += 2
        elif nxt == "u" and i + 6 <= n:
            out.append(chr(int(s[i + 2 : i + 6], 16)))
            i += 6
        elif nxt == "x" and i + 4 <= n:
            out.append(chr(int(s[i + 2 : i + 4], 16)))
            i += 4
        else:
            out.append(nxt)
            i += 2
    return "".join(out)


def extract_js_push_strings(html: str) -> str:
    raw_parts: list[str] = []
    needle = "self.__next_f.push([1,"
    start = 0
    while True:
        i = html.find(needle, start)
        if i < 0:
            break
        j = i + len(needle)
        while j < len(html) and html[j] in " \t\n":
            j += 1
        if j >= len(html) or html[j] != '"':
            start = j
            continue
        j += 1
        body_start = j
        while j < len(html):
            if html[j] == "\\" :
                j += 2
                continue
            if html[j] == '"':
                raw_parts.append(unescape_js_string(html[body_start:j]))
                break
            j += 1
        start = j + 1
    return "".join(raw_parts)


def extract_json_object(s: str, start: int) -> str:
    if start < 0 or start >= len(s) or s[start] != "{":
        raise ValueError("no JSON object at start index")
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(s)):
        c = s[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return s[start : j + 1]
    raise ValueError("unbalanced JSON object")


def parse_marketplace_html(html: str) -> dict[str, Any]:
    payload = extract_js_push_strings(html)
    idx = payload.find('{"featured"')
    if idx < 0:
        raise RuntimeError("could not find marketplace payload in page HTML")
    data = json.loads(extract_json_object(payload, idx))
    if "templates" not in data or "featured" not in data:
        raise RuntimeError("marketplace payload missing templates or featured")
    return data


def fetch_listing(slug: str) -> dict[str, Any] | None:
    body = json.dumps({"slug": slug}).encode()
    status, _headers, raw = request(
        LISTING_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Connect-Protocol-Version": "1",
        },
        method="POST",
        timeout=30,
    )
    if status != 200:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def iso_from_ms(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def check_url(url: str) -> dict[str, Any]:
    """Return live status for a public URL. HEAD, then GET if HEAD is rejected."""
    result: dict[str, Any] = {"url": url, "ok": False, "status": None, "final_url": url}
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                method=method,
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                result["status"] = resp.status
                result["final_url"] = resp.geturl()
                result["ok"] = 200 <= resp.status < 400
                if result["ok"] or method == "GET":
                    return result
        except urllib.error.HTTPError as exc:
            result["status"] = exc.code
            # Some hosts reject HEAD with 405/403; try GET.
            if method == "HEAD" and exc.code in (403, 405, 501):
                continue
            result["ok"] = False
            return result
        except Exception as exc:  # noqa: BLE001
            result["error"] = type(exc).__name__
            if method == "HEAD":
                continue
            result["ok"] = False
            return result
    return result


def normalize_template(
    raw: dict[str, Any],
    *,
    featured_ids: set[str],
    listing: dict[str, Any] | None,
) -> dict[str, Any]:
    slug = raw["id"]
    share_path = raw.get("addHref") or ""
    share_id = share_path.rsplit("/", 1)[-1] if share_path else None
    listing_obj = (listing or {}).get("listing") or {}
    if listing_obj.get("shareId"):
        share_id = listing_obj["shareId"]
    creator = listing_obj.get("creator") or {}
    handles = creator.get("handles") or {}
    handle = raw.get("handle") or handles.get("x") or None
    # Prefer the longer public listing description when present.
    description = (
        (listing_obj.get("description") or "").strip()
        or (raw.get("description") or raw.get("summary") or "").strip()
    )
    categories = list(raw.get("categories") or listing_obj.get("categories") or [])
    updated = raw.get("updatedAt")
    if updated and not str(updated).endswith("Z") and "+" not in str(updated):
        # Keep the catalog timestamp as-is; also record listing clocks.
        pass
    entry = {
        "slug": slug,
        "name": listing_obj.get("name") or raw.get("name") or slug,
        "description": description,
        "categories": categories,
        "featured": slug in featured_ids,
        "creator_name": listing_obj.get("creator", {}).get("name")
        or raw.get("creatorName")
        or None,
        "creator_handle": handle,
        "marketplace_url": f"https://x.ai/bot/marketplace/bots/{slug}",
        "share_url": f"https://x.ai/bot/{share_id}" if share_id else None,
        "share_id": share_id,
        "updated_at": raw.get("updatedAt"),
        "created_at": iso_from_ms(listing_obj.get("createdAtMs")),
        "listing_updated_at": iso_from_ms(listing_obj.get("updatedAtMs")),
        "image_url": raw.get("imageUrl"),
        "marketplace_url_ok": None,
        "share_url_ok": None,
    }
    return entry


def write_marketplace_readme(
    path: Path,
    *,
    fetched_at: str,
    entries: list[dict[str, Any]],
    dropped: list[dict[str, Any]],
    featured_ids: list[str],
) -> None:
    by_slug = {e["slug"]: e for e in entries}
    lines: list[str] = []
    lines.append("# Marketplace index")
    lines.append("")
    lines.append(
        f"Every template listed on the official [Grok Bot marketplace]({MARKETPLACE_URL}) "
        f"as of {fetched_at}. {len(entries)} live templates. "
        "A bot can appear in more than one category, matching the official catalog."
    )
    lines.append("")
    lines.append(
        "Refresh this file with `python3 scripts/refresh_marketplace.py`. "
        "Machine-readable data lives in [`../data/marketplace.json`](../data/marketplace.json)."
    )
    lines.append("")
    lines.append("## Contents")
    lines.append("")
    lines.append("- [Featured](#featured)")
    for title, slug in CATEGORY_PAGES:
        anchor = slug
        lines.append(f"- [{title}](#{anchor})")
    uncategorized = [
        e
        for e in entries
        if not e.get("categories") and e["slug"] not in featured_ids
    ]
    featured_only = [
        e
        for e in entries
        if not e.get("categories") and e["slug"] in featured_ids
    ]
    # Featured-only bots still have a heading under Featured, no extra section needed
    # unless some have neither featured nor categories.
    if uncategorized:
        lines.append("- [Uncategorized](#uncategorized)")
    if dropped:
        lines.append("- [Dropped (dead links)](#dropped-dead-links)")
    lines.append("")

    def bot_line(entry: dict[str, Any]) -> str:
        name = entry["name"]
        url = entry.get("share_url") or entry["marketplace_url"]
        catalog = entry["marketplace_url"]
        creator = entry.get("creator_name") or "unknown"
        handle = entry.get("creator_handle")
        by = f"{creator}"
        if handle:
            by = f"{creator} ([@{handle}](https://x.com/{handle}))"
        desc = (entry.get("description") or "").replace("\n", " ").strip()
        # One line: name, creator, description, catalog link if share is primary.
        parts = [f"- [{name}]({url}) by {by}."]
        if desc:
            parts.append(desc)
        if entry.get("share_url") and catalog:
            parts.append(f"[Catalog page]({catalog}).")
        return " ".join(parts)

    lines.append("## Featured")
    lines.append("")
    lines.append("The featured rail on the marketplace homepage.")
    lines.append("")
    for slug in featured_ids:
        if slug in by_slug:
            lines.append(bot_line(by_slug[slug]))
    lines.append("")

    for title, page_slug in CATEGORY_PAGES:
        lines.append(f"## {title}")
        lines.append("")
        lines.append(
            f"Official category: [x.ai/bot/marketplace/{page_slug}]"
            f"(https://x.ai/bot/marketplace/{page_slug})."
        )
        lines.append("")
        members = [
            e
            for e in entries
            if title in (e.get("categories") or [])
        ]
        members.sort(key=lambda e: e["name"].lower())
        if not members:
            lines.append("No live templates in this category right now.")
            lines.append("")
            continue
        for entry in members:
            lines.append(bot_line(entry))
        lines.append("")

    if uncategorized:
        lines.append("## Uncategorized")
        lines.append("")
        lines.append("Live templates that the catalog did not assign to a category.")
        lines.append("")
        for entry in sorted(uncategorized, key=lambda e: e["name"].lower()):
            lines.append(bot_line(entry))
        lines.append("")

    if dropped:
        lines.append("## Dropped (dead links)")
        lines.append("")
        lines.append(
            "These were in the catalog payload but their public pages did not resolve "
            "when this index was generated, so they are omitted from the lists above."
        )
        lines.append("")
        for item in dropped:
            name = item.get("name") or item.get("slug")
            reason = item.get("drop_reason") or "dead link"
            url = item.get("marketplace_url") or item.get("share_url") or ""
            if url:
                lines.append(f"- {name} ({reason}): {url}")
            else:
                lines.append(f"- {name} ({reason})")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        help="Do not call GetPublicGrokBotMarketplaceListing for longer descriptions.",
    )
    parser.add_argument(
        "--skip-link-check",
        action="store_true",
        help="Do not HTTP-check marketplace and share URLs.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Parallel workers for listing enrich and link checks (default 8).",
    )
    args = parser.parse_args()

    fetched_at = utc_now_iso()
    print(f"Fetching {MARKETPLACE_URL} ...", file=sys.stderr)
    status, _headers, raw = request(MARKETPLACE_URL, timeout=45)
    if status != 200:
        print(f"error: marketplace page returned HTTP {status}", file=sys.stderr)
        return 1
    html = raw.decode("utf-8")
    payload = parse_marketplace_html(html)
    featured_ids = [b["id"] for b in payload["featured"]["bots"]]
    templates = payload["templates"]
    print(f"Parsed {len(templates)} templates, {len(featured_ids)} featured.", file=sys.stderr)

    listings: dict[str, dict[str, Any] | None] = {}
    if not args.skip_enrich:
        print("Enriching from public listing API ...", file=sys.stderr)
        slugs = [t["id"] for t in templates]

        def _one(slug: str) -> tuple[str, dict[str, Any] | None]:
            return slug, fetch_listing(slug)

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for slug, listing in pool.map(_one, slugs):
                listings[slug] = listing
                if listing is None:
                    print(f"  warning: no listing for {slug}", file=sys.stderr)
        print(
            f"  enriched {sum(1 for v in listings.values() if v)}/{len(slugs)}",
            file=sys.stderr,
        )
        time.sleep(0.1)

    entries = [
        normalize_template(
            t,
            featured_ids=set(featured_ids),
            listing=listings.get(t["id"]),
        )
        for t in templates
    ]

    dropped: list[dict[str, Any]] = []
    live: list[dict[str, Any]] = []
    if args.skip_link_check:
        for e in entries:
            e["marketplace_url_ok"] = None
            e["share_url_ok"] = None
            live.append(e)
    else:
        print("Checking marketplace and share URLs ...", file=sys.stderr)
        urls: list[tuple[str, str, str]] = []  # slug, kind, url
        for e in entries:
            urls.append((e["slug"], "marketplace", e["marketplace_url"]))
            if e.get("share_url"):
                urls.append((e["slug"], "share", e["share_url"]))

        results: dict[tuple[str, str], dict[str, Any]] = {}

        def _check(item: tuple[str, str, str]) -> tuple[tuple[str, str], dict[str, Any]]:
            slug, kind, url = item
            return (slug, kind), check_url(url)

        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            for key, res in pool.map(_check, urls):
                results[key] = res

        for e in entries:
            m = results.get((e["slug"], "marketplace"))
            s = results.get((e["slug"], "share"))
            e["marketplace_url_ok"] = bool(m and m.get("ok"))
            e["share_url_ok"] = bool(s and s.get("ok")) if e.get("share_url") else None
            if e.get("share_url") and not e["share_url_ok"]:
                # Keep the catalog link if it still works; drop only the share URL.
                print(
                    f"  dead share URL for {e['slug']}: {e['share_url']} "
                    f"(status {None if not s else s.get('status')})",
                    file=sys.stderr,
                )
                e["share_url"] = None
                e["share_id"] = None
            if not e["marketplace_url_ok"] and not e["share_url_ok"]:
                e["drop_reason"] = (
                    f"marketplace HTTP {None if not m else m.get('status')}, "
                    f"share HTTP {None if not s else s.get('status')}"
                )
                dropped.append(e)
            else:
                live.append(e)
        print(
            f"  live {len(live)}, dropped {len(dropped)}, "
            f"share URLs removed {sum(1 for e in live if e.get('share_url') is None)}",
            file=sys.stderr,
        )

    data_path = REPO_ROOT / "data" / "marketplace.json"
    readme_path = REPO_ROOT / "marketplace" / "README.md"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.parent.mkdir(parents=True, exist_ok=True)

    document = {
        "source": MARKETPLACE_URL,
        "fetched_at": fetched_at,
        "template_count": len(live),
        "dropped_count": len(dropped),
        "featured": featured_ids,
        "categories": [title for title, _slug in CATEGORY_PAGES],
        "templates": live,
        "dropped": [
            {
                "slug": d.get("slug"),
                "name": d.get("name"),
                "marketplace_url": d.get("marketplace_url"),
                "share_url": d.get("share_url"),
                "drop_reason": d.get("drop_reason"),
            }
            for d in dropped
        ],
        "notes": [
            "Source is the public RSC payload on https://x.ai/bot/marketplace.",
            "Descriptions may be enriched from GetPublicGrokBotMarketplaceListing.",
            "installCount on the public page is currently always 0, so it is omitted.",
            "Pre-signed recipe download URLs are never stored.",
        ],
    }
    data_path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_marketplace_readme(
        readme_path,
        fetched_at=fetched_at,
        entries=live,
        dropped=dropped,
        featured_ids=featured_ids,
    )
    print(f"Wrote {data_path} ({len(live)} templates).", file=sys.stderr)
    print(f"Wrote {readme_path}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
