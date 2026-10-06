#!/usr/bin/env python3
"""Render the publication archive as static HTML, enhancing it with optional filters."""

import html
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def escape(value):
    return html.escape(str(value), quote=True)


def date_label(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d %b %Y") if value else "date unavailable"


def safe_url(value):
    value = str(value or "")
    return value if value.startswith("https://") or (value.startswith("/") and not value.startswith("//")) else ""


def link(url, label):
    url = safe_url(url)
    if not url:
        return ""
    external = ' target="_blank" rel="noopener"' if url.startswith("https://") else ""
    return f'<a href="{escape(url)}"{external}>{escape(label)}</a>'


def render(data):
    publications = data["publications"]
    topics = sorted({topic for publication in publications for topic in publication.get("topics", [])})
    years = sorted({str(p.get("year", "n.d.")) for p in publications}, reverse=True)
    controls = '''<form class="publication-tools" id="publication-filters" hidden role="search" aria-label="Filter publications">
      <div class="search-field"><label for="publication-search">Search publications</label>
      <input id="publication-search" class="publication-search" type="search" placeholder="Title, author, journal or DOI" aria-controls="publication-list" /></div>
      <div><label for="publication-topic">Topic</label><select id="publication-topic"><option value="">All topics</option>'''
    controls += "".join(f'<option value="{escape(topic)}">{escape(topic)}</option>' for topic in topics)
    controls += '</select></div><div><label for="publication-year">Year</label><select id="publication-year"><option value="">All years</option>'
    controls += "".join(f'<option value="{escape(year)}">{escape(year)}</option>' for year in years)
    controls += '</select></div><button class="button" type="reset">Clear filters</button></form>'
    metrics = data.get("metrics", {})
    summary = ""
    if metrics:
        summary = f'''<p class="scholar-summary">Google Scholar profile: <strong>{escape(metrics.get('citations', '—'))} citations</strong> ·
        h-index {escape(metrics.get('h_index', '—'))} · i10-index {escape(metrics.get('i10_index', '—'))}.
        Verified {date_label(data.get('updated_at'))}.</p>'''
    rendered = []
    for publication in publications:
        topics_json = escape(json.dumps(publication.get("topics", []), ensure_ascii=False))
        doi_url = "https://doi.org/" + publication["doi"] if publication.get("doi") else ""
        page = safe_url(publication.get("page_url"))
        scholar = safe_url(publication.get("scholar_url"))
        primary = page or doi_url or scholar or data["profile_url"]
        actions = [link(page, "Publication page"), link(doi_url, "Read via DOI")]
        # Only curated permitted access links are rendered; never infer a PDF URL.
        actions += [link(publication.get("open_url"), "Open access"), link(publication.get("eprint_url"), "PDF / eprint"), link(scholar, "Google Scholar")]
        citations = []
        if "citations" in publication:
            citations.append(f"Google Scholar: {escape(publication['citations'])} citations ({date_label(publication.get('citations_updated_at', data.get('updated_at')))})")
        if "crossref_citations" in publication:
            citations.append(f"Crossref: {escape(publication['crossref_citations'])} citations ({date_label(publication.get('crossref_updated_at'))})")
        status = f'<span class="tag orange">{escape(publication["status"])}</span>' if publication.get("status") else ""
        rendered.append(f'''<article class="publication" data-year="{escape(publication.get('year', 'n.d.'))}" data-topics="{topics_json}">
          <div class="year">{escape(publication.get('year', 'n.d.'))}</div><div>{status}
          <h3>{link(primary, publication['title'])}</h3>
          <p>{escape(publication.get('authors', ''))}<br /><em>{escape(publication.get('venue', ''))}</em></p>
          {f'<p class="doi-line">DOI: {link(doi_url, publication["doi"])}</p>' if doi_url else ''}
          <p class="citation-line">{'<br />'.join(citations)}</p>
          <div class="publication-actions">{''.join(actions)}</div></div></article>''')
    return f'''{summary}
    {controls}
    <p id="publication-meta" class="publication-meta" role="status" aria-live="polite">{len(publications)} publications</p>
    <div id="publication-list">{''.join(rendered)}</div>
    <p id="publication-empty" hidden>No publications match these filters. Try another search or clear the filters.</p>'''


def main():
    data = json.loads((ROOT / "publications.json").read_text())
    path = ROOT / "publications/index.html"
    original = path.read_text()
    pattern = r"<!-- PUBLICATIONS:START -->.*?<!-- PUBLICATIONS:END -->"
    replacement = "<!-- PUBLICATIONS:START -->\n" + render(data) + "\n<!-- PUBLICATIONS:END -->"
    updated, count = re.subn(pattern, lambda _: replacement, original, flags=re.S)
    if count != 1:
        raise ValueError("The publication HTML needs exactly one pair of rendering markers.")
    if updated != original:
        path.write_text(updated)
    # Advance only the archive's sitemap date when the rendered archive actually changed.
    if updated != original:
        sitemap = ROOT / "sitemap.xml"
        xml = sitemap.read_text()
        timestamps = [data.get("updated_at", ""), data.get("crossref_updated_at", "")]
        stamp = max(timestamps)[:10]
        if stamp:
            xml = re.sub(r"(<loc>https://borisvazquezcalvo.com/publications/</loc>\s*<lastmod>)[^<]+", lambda m: m[1] + stamp, xml)
            sitemap.write_text(xml)
    print(f"Rendered {len(data['publications'])} publications as static HTML.")


if __name__ == "__main__":
    main()
