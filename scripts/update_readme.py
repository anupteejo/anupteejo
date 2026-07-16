#!/usr/bin/env python3
"""Refresh the auto-generated blocks in README.md.

Publication metadata (title/journal/year/DOI) is pulled fresh from the
public ORCID API (no key required), then filtered down to a curated
list of "highlighted" DOIs below, in that order -- ORCID has no notion
of which papers are highlights, so that curation is a static list here
rather than something an API can derive.

Citation metrics come from Scopus (Elsevier Author Retrieval API) and
Google Scholar (via SerpApi) *only* if the corresponding API key is
supplied through the SCOPUS_API_KEY / SERPAPI_KEY environment
variables. Without a key, that source is rendered as a plain badge
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

# Curated, in display order. Edit this list to change what shows up
# under "Highlighted publications" -- everything else is fetched live.
HIGHLIGHTED_DOIS = [
    "10.1177/02783649251346209",  # Analytical Derivatives of Strain-Based Dynamic Model for Hybrid Soft-Rigid Robots, IJRR 2025
    "10.1177/02783649241262333",  # Reduced Order Modeling of Hybrid Soft-Rigid Robots ..., IJRR 2024
    "10.1109/MRA.2022.3202488",   # SoRoSim: A MATLAB Toolbox for Hybrid Rigid-Soft Robots ..., RAM 2022
    "10.1109/TRO.2024.3522182",   # Soft Synergies: Model Order Reduction of Hybrid Soft-Rigid Robots ..., TRO 2025
    "10.1089/soro.2024.0036",     # ZodiAq: An Isotropic Flagella-Inspired Soft Underwater Drone ..., Soft Robotics 2025
]


def fetch_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def get_orcid_works():
    data = fetch_json(
        f"https://pub.orcid.org/v3.0/{ORCID_ID}/works",
        headers={"Accept": "application/json"},
    )
    by_doi = {}
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
        year = int(year_raw) if year_raw else None
        doi = None
        for ext in ((w.get("external-ids") or {}).get("external-id") or []):
            if ext.get("external-id-type") == "doi":
                doi = ext.get("external-id-value")
                break
        if doi:
            by_doi[doi.lower()] = {"title": title, "journal": journal, "year": year, "doi": doi}
    return by_doi


def get_highlighted_publications():
    by_doi = get_orcid_works()

    lines = []
    for doi in HIGHLIGHTED_DOIS:
        e = by_doi.get(doi.lower())
        if not e:
            continue
        line = f"- **{e['title']}**"
        if e["journal"]:
            line += f". *{e['journal']}*"
        if e["year"]:
            line += f", {e['year']}"
        line += f". [DOI](https://doi.org/{e['doi']})"
        lines.append(line)

    if not lines:
        lines.append("- _Could not fetch publications from ORCID this run._")

    lines.append("")
    lines.append(f"[Full publication list on ORCID](https://orcid.org/{ORCID_ID})")
    return "\n".join(lines)


def badge(label, message, color):
    def esc(s):
        return str(s).replace("-", "--").replace(" ", "_")
    return f"https://img.shields.io/badge/{esc(label)}-{esc(message)}-{color}?style=flat-square"


def get_scopus_metrics():
    profile_url = f"https://www.scopus.com/authid/detail.uri?authorId={SCOPUS_AUTHOR_ID}"
    api_key = os.environ.get("SCOPUS_API_KEY")
    message = "profile"
    if api_key:
        try:
            data = fetch_json(
                f"https://api.elsevier.com/content/author/author_id/{SCOPUS_AUTHOR_ID}"
                "?field=citation-count,h-index,document-count",
                headers={"X-ELS-APIKey": api_key, "Accept": "application/json"},
            )
            core = data["author-retrieval-response"][0]
            citations = core["coredata"]["citation-count"]
            h_index = core["h-index"]
            message = f"{citations} citations, h-index {h_index}"
        except Exception:
            pass
    return f"[![Scopus]({badge('Scopus', message, 'E9711C')})]({profile_url})"


def get_scholar_metrics():
    profile_url = f"https://scholar.google.com/citations?user={SCHOLAR_USER_ID}&hl=en"
    api_key = os.environ.get("SERPAPI_KEY")
    message = "profile"
    if api_key:
        try:
            data = fetch_json(
                "https://serpapi.com/search.json"
                f"?engine=google_scholar_author&author_id={SCHOLAR_USER_ID}&api_key={api_key}"
            )
            table = data["cited_by"]["table"]
            citations = table[0]["citations"]["all"]
            h_index = table[1]["h_index"]["all"]
            message = f"{citations} citations, h-index {h_index}"
        except Exception:
            pass
    return f"[![Google Scholar]({badge('Google_Scholar', message, '4285F4')})]({profile_url})"


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

    metrics = f"{get_scholar_metrics()} {get_scopus_metrics()}"
    content = replace_block(content, "METRICS", metrics)
    content = replace_block(content, "HIGHLIGHTS", get_highlighted_publications())

    README.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
