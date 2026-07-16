#!/usr/bin/env python3
"""Refresh the auto-generated blocks in README.md.

Publications are pulled from the public ORCID API (no key required).
Citation metrics come from Scopus (Elsevier Author Retrieval API) and
Google Scholar (via SerpApi) *only* if the corresponding API key is
supplied through the SCOPUS_API_KEY / SERPAPI_KEY environment
variables. Without a key, that source is rendered as a plain profile
link with no numbers, since there is no way to fetch it reliably
(Google Scholar has no public API and blocks scripted access; Scopus
requires a registered key).
"""
import json
import os
import re
import urllib.request
from pathlib import Path

ORCID_ID = "0000-0003-4022-7501"
SCOPUS_AUTHOR_ID = "57194901986"
SCHOLAR_USER_ID = "1ezZWI8AAAAJ"

README = Path(__file__).resolve().parent.parent / "README.md"
MAX_PUBLICATIONS = 15


def fetch_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def get_publications():
    data = fetch_json(
        f"https://pub.orcid.org/v3.0/{ORCID_ID}/works",
        headers={"Accept": "application/json"},
    )
    entries = []
    for group in data.get("group", []):
        summaries = group.get("work-summary", [])
        if not summaries:
            continue
        w = summaries[0]
        title = (w.get("title") or {}).get("title", {}).get("value")
        if not title:
            continue
        journal = (w.get("journal-title") or {}).get("value")
        year_raw = ((w.get("publication-date") or {}).get("year") or {}).get("value")
        year = int(year_raw) if year_raw else 0
        doi = None
        for ext in ((w.get("external-ids") or {}).get("external-id") or []):
            if ext.get("external-id-type") == "doi":
                doi = ext.get("external-id-value")
                break
        entries.append({"title": title, "journal": journal, "year": year, "doi": doi})

    entries.sort(key=lambda e: e["year"], reverse=True)

    lines = []
    for e in entries[:MAX_PUBLICATIONS]:
        line = f"- **{e['title']}**"
        if e["journal"]:
            line += f". *{e['journal']}*"
        if e["year"]:
            line += f", {e['year']}"
        if e["doi"]:
            line += f". [DOI](https://doi.org/{e['doi']})"
        lines.append(line)

    if not lines:
        lines.append("- _Could not fetch publications from ORCID this run._")

    lines.append("")
    lines.append(f"[Full list on ORCID](https://orcid.org/{ORCID_ID})")
    return "\n".join(lines)


def get_scopus_metrics():
    api_key = os.environ.get("SCOPUS_API_KEY")
    profile_link = f"[Scopus](https://www.scopus.com/authid/detail.uri?authorId={SCOPUS_AUTHOR_ID})"
    if not api_key:
        return profile_link
    try:
        data = fetch_json(
            f"https://api.elsevier.com/content/author/author_id/{SCOPUS_AUTHOR_ID}"
            "?field=citation-count,h-index,document-count",
            headers={"X-ELS-APIKey": api_key, "Accept": "application/json"},
        )
        core = data["author-retrieval-response"][0]
        citations = core["coredata"]["citation-count"]
        h_index = core["h-index"]
        return f"{profile_link}: {citations} citations, h-index {h_index}"
    except Exception:
        return profile_link


def get_scholar_metrics():
    api_key = os.environ.get("SERPAPI_KEY")
    profile_link = f"[Google Scholar](https://scholar.google.com/citations?user={SCHOLAR_USER_ID}&hl=en)"
    if not api_key:
        return profile_link
    try:
        data = fetch_json(
            "https://serpapi.com/search.json"
            f"?engine=google_scholar_author&author_id={SCHOLAR_USER_ID}&api_key={api_key}"
        )
        table = data["cited_by"]["table"]
        citations = table[0]["citations"]["all"]
        h_index = table[1]["h_index"]["all"]
        return f"{profile_link}: {citations} citations, h-index {h_index}"
    except Exception:
        return profile_link


def replace_block(content, marker, new_text):
    pattern = re.compile(
        rf"(<!-- {marker}:START -->)(.*?)(<!-- {marker}:END -->)", re.DOTALL
    )
    replacement = f"\\1\n{new_text}\n\\3"
    if not pattern.search(content):
        raise SystemExit(f"Marker block {marker} not found in README.md")
    return pattern.sub(replacement, content)


def main():
    content = README.read_text(encoding="utf-8")

    metrics = f"- {get_scholar_metrics()}\n- {get_scopus_metrics()}"
    content = replace_block(content, "METRICS", metrics)
    content = replace_block(content, "PUBLICATIONS", get_publications())

    README.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
