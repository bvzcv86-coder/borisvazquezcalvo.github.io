# Boris Vázquez-Calvo’s academic website

The publication archive includes 15 selected works with readable research pages,
verified reading links, citation metadata and RIS/BibTeX downloads. Six papers have
unchanged, licensed PDF copies with optional previews. The recent AI article also
has reference downloads; its PDF is not hosted while access conditions apply.

To update a research summary or a verified access link, edit
`publication-pages.json`. Bibliographic details remain in `publications.json`.
Then regenerate the pages and reference files:

```sh
python scripts/build_publication_pages.py
python scripts/render_publications.py
```

Keep creator names and editor roles as printed in the source publication. Use
the final issue year in references and retain an earlier online date as a note.
Add hosted PDFs only after checking distribution terms, preserve the original
file and supply its source and licence. The weekly citation workflow preserves
these curated fields and renders only the archive region.

**Language learning, teaching, and digital practices.**

Static HTML website served by GitHub Pages at https://borisvazquezcalvo.com.

The navigation includes Home, Research, Topics, Publications, News, Projects,
Open Materials, Talks, Teaching and Contact. Native disclosure menus work with
keyboard and touch, including without JavaScript.

## Publication maintenance

`publications.json` is the curated source. Publisher metadata, DOI links, topic
tags and permitted open-access links are maintained there. Scholar identities
allow citation updates to preserve corrected titles and publication years.

Run with Python 3.11 or later (standard library only):

```
python scripts/update_scholar.py
python scripts/update_crossref.py
python scripts/render_publications.py
```

The weekly GitHub workflow tries Scholar and independently refreshes Crossref
counts for DOI records. Scholar may block GitHub runner IPs with HTTP 403; that
failure preserves the last successful Scholar snapshot. Each source and its
verification date are displayed separately. Crossref has different coverage
from Scholar and its counts must never be labelled as Scholar counts.

The renderer writes only the marked publication region and its sitemap date,
leaving the rest of the page editable. The full archive is readable without
JavaScript; optional JavaScript adds search and year/topic filters.

The AI article is linked through its DOI and publisher; its PDF is not served
by this website. The permitted Language Learning & Technology PDF remains.

GitHub Pages serves the `main` branch root. The workflow commits updated JSON,
rendered HTML and sitemap, then explicitly requests and verifies a Pages build.
