import json
from datetime import datetime, timezone
from scholarly import scholarly


SCHOLAR_ID = "qcOWEqgAAAAJ"
OUTPUT_FILE = "publications.json"


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def main():
    author = scholarly.search_author_id(SCHOLAR_ID)

    # Lightweight fill: only profile basics, indices, and publication list.
    # This avoids opening each publication individually, which can hang or trigger blocks.
    author = scholarly.fill(author, sections=["basics", "indices", "publications"])

    publications = []

    for pub in author.get("publications", []):
        bib = pub.get("bib", {})

        title = clean(bib.get("title"))
        authors = clean(bib.get("author"))
        venue = clean(
            bib.get("venue")
            or bib.get("journal")
            or bib.get("booktitle")
            or bib.get("publisher")
        )
        year = clean(bib.get("pub_year"))
        citations = pub.get("num_citations", 0)

        if not title:
            continue

        publications.append({
            "year": year,
            "title": title,
            "authors": authors,
            "venue": venue,
            "citations": citations,
            "scholar_url": f"https://scholar.google.com/citations?user={SCHOLAR_ID}&hl=en&oi=ao",
            "eprint_url": "",
            "doi": ""
        })

    publications = sorted(
        publications,
        key=lambda x: (
            int(x["year"]) if str(x["year"]).isdigit() else 0,
            int(x["citations"]) if str(x["citations"]).isdigit() else 0
        ),
        reverse=True
    )

    output = {
        "source": "Google Scholar",
        "scholar_id": SCHOLAR_ID,
        "profile_url": f"https://scholar.google.com/citations?user={SCHOLAR_ID}&hl=en&oi=ao",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_publications": len(publications),
        "publications": publications
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(publications)} publications to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
