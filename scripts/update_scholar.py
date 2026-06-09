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
    author = scholarly.fill(author, sections=["publications", "basics", "indices"])

    publications = []

    for pub in author.get("publications", []):
        try:
            pub_filled = scholarly.fill(pub)
            bib = pub_filled.get("bib", {})

            title = clean(bib.get("title"))
            authors = clean(bib.get("author"))
            venue = clean(
                bib.get("venue")
                or bib.get("journal")
                or bib.get("booktitle")
                or bib.get("publisher")
            )
            year = clean(bib.get("pub_year"))
            citations = pub_filled.get("num_citations", 0)

            scholar_url = pub_filled.get("pub_url") or pub_filled.get("eprint_url") or ""
            eprint_url = pub_filled.get("eprint_url") or ""
            doi = ""

            publications.append({
                "year": year,
                "title": title,
                "authors": authors,
                "venue": venue,
                "citations": citations,
                "scholar_url": scholar_url,
                "eprint_url": eprint_url,
                "doi": doi
            })

        except Exception as e:
            print(f"Skipping one publication because of error: {e}")

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
