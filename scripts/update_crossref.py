#!/usr/bin/env python3
"""Update DOI-based Crossref counts without modifying Scholar counts or metadata."""

import json
import sys
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from update_scholar import DEFAULT_FILE, write_json_atomic


def fetch_count(doi):
    url = "https://api.crossref.org/works/" + quote(doi, safe="")
    request = Request(url, headers={"User-Agent": "BorisAcademicWebsite/1.0 (https://borisvazquezcalvo.com/)", "Accept": "application/json"})
    for attempt in range(2):
        try:
            with urlopen(request, timeout=20) as response:
                record = json.load(response)["message"]
            if record.get("DOI", "").casefold() != doi.casefold():
                raise ValueError("Crossref returned a different DOI")
            count = record.get("is-referenced-by-count")
            if type(count) is not int or count < 0:
                raise ValueError("Crossref citation count is missing or invalid")
            return count
        except HTTPError as error:
            if error.code == 404:
                return None  # Not all DOIs are registered with Crossref.
            if error.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(min(int(error.headers.get("Retry-After", "3")), 30))
                continue
            raise
        except (URLError, TimeoutError):
            if attempt == 0:
                time.sleep(2)
                continue
            raise


def main():
    data = json.loads(DEFAULT_FILE.read_text())
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    refreshed = 0
    for publication in data["publications"]:
        doi = publication.get("doi", "").strip()
        if not doi:
            continue
        try:
            count = fetch_count(doi)
            if count is not None:
                publication["crossref_citations"] = count
                publication["crossref_updated_at"] = timestamp
                refreshed += 1
            else:
                print(f"Crossref has no record for {doi}; existing counts preserved.")
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as error:
            print(f"::warning::Crossref {doi}: {error}; existing counts preserved.")
        time.sleep(0.25)
    if not refreshed:
        print("No Crossref counts could be refreshed; no JSON was overwritten.", file=sys.stderr)
        return 1
    data["crossref_updated_at"] = timestamp
    data["crossref_publications_refreshed"] = refreshed
    write_json_atomic(DEFAULT_FILE, data)
    print(f"Refreshed Crossref counts for {refreshed} publications. Scholar data and curated metadata preserved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
