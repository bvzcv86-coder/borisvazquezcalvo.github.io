#!/usr/bin/env python3
"""Refresh Scholar citations without replacing curated publication metadata.

Run from GitHub Actions or locally with Python 3.11 or later.
Only Python's standard library is required.
"""

import argparse
import copy
import json
import math
import os
import re
import sys
import tempfile
import time
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen


SCHOLAR_ID = "qcOWEqgAAAAJ"
PROFILE_URL = f"https://scholar.google.com/citations?user={SCHOLAR_ID}&hl=en"
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "publications.json"

PAGE_SIZE = 100
MAX_PAGES = 10
REQUEST_TIMEOUT = 20
MIN_MATCH_RATIO = 0.90

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}


class UpdateError(Exception):
    """An update that cannot safely be published."""


class Node:
    def __init__(self, tag="", attrs=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children = []

    def text(self):
        return "".join(
            child.text() if isinstance(child, Node) else child
            for child in self.children
        ).strip()

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()

    def find_all(self, predicate):
        matches = []

        for child in self.children:
            if isinstance(child, Node):
                if predicate(child):
                    matches.append(child)

                matches.extend(child.find_all(predicate))

        return matches


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)

        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, dict(attrs)))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def first(nodes, description):
    if not nodes:
        raise UpdateError(
            f"Missing {description}; Scholar may have blocked the request."
        )

    return nodes[0]


def number(text, allow_zero_blank=False):
    value = text.strip()

    if not value and allow_zero_blank:
        return 0

    if not re.fullmatch(r"\d+(?:,\d{3})*\*?", value):
        raise UpdateError(
            f"Unexpected citation or metric value: {value!r}"
        )

    return int(value.replace(",", "").rstrip("*"))


def parse_page(html):
    parser = PageParser()
    parser.feed(html)
    root = parser.root

    table = first(
        root.find_all(
            lambda node: node.attrs.get("id") == "gsc_a_b"
        ),
        "publication table",
    )

    publications = []

    for row in table.find_all(lambda node: node.tag == "tr"):
        cells = [
            node
            for node in row.children
            if isinstance(node, Node) and node.tag == "td"
        ]

        if len(cells) != 3:
            raise UpdateError(
                "Unexpected publication row; refusing a partial update."
            )

        link = first(
            cells[0].find_all(
                lambda node: node.has_class("gsc_a_at")
            ),
            "article title",
        )

        query = parse_qs(
            urlsplit(link.attrs.get("href", "")).query
        )

        publication_id = query.get(
            "citation_for_view", [""]
        )[0]

        if (
            not publication_id.startswith(SCHOLAR_ID + ":")
            or not link.text()
        ):
            raise UpdateError(
                "Article identifier does not belong to the expected "
                "Scholar profile."
            )

        publications.append({
            "id": publication_id,
            "title": link.text(),
            "year": cells[2].text(),
            "citations": number(
                cells[1].text(),
                allow_zero_blank=True,
            ),
            "scholar_url": (
                "https://scholar.google.com/citations?"
                + urlencode({
                    "view_op": "view_citation",
                    "hl": "en",
                    "user": SCHOLAR_ID,
                    "citation_for_view": publication_id,
                })
            ),
        })

    if not publications:
        raise UpdateError(
            "Scholar returned no articles; the existing JSON "
            "will be preserved."
        )

    more = first(
        root.find_all(
            lambda node: node.attrs.get("id") == "gsc_bpf_more"
        ),
        "pagination control",
    )

    has_more = "disabled" not in more.attrs

    metrics_table = first(
        root.find_all(
            lambda node: node.attrs.get("id") == "gsc_rsb_st"
        ),
        "profile metrics",
    )

    metrics = {}

    metric_keys = {
        "citations": "citations",
        "h-index": "h_index",
        "i10-index": "i10_index",
    }

    for row in metrics_table.find_all(
        lambda node: node.tag == "tr"
    ):
        cells = row.find_all(
            lambda node: node.tag in {"td", "th"}
        )

        recent = re.search(r"Since\s+(\d{4})", row.text())

        if recent:
            metrics["since_year"] = int(recent.group(1))

        if (
            len(cells) == 3
            and cells[0].text().casefold() in metric_keys
        ):
            key = metric_keys[cells[0].text().casefold()]
            metrics[key] = number(cells[1].text())
            metrics[key + "_since"] = number(cells[2].text())

    if len(metrics) != 7:
        raise UpdateError(
            "Incomplete Scholar metrics; the existing JSON "
            "will be preserved."
        )

    return publications, metrics, has_more


def download_page(start):
    url = (
        "https://scholar.google.com/citations?"
        + urlencode({
            "user": SCHOLAR_ID,
            "hl": "en",
            "cstart": start,
            "pagesize": PAGE_SIZE,
        })
    )

    request = Request(
        url,
        headers={
            "User-Agent": (
                "BorisVazquezCalvoWebsite/1.0 "
                "(+https://borisvazquezcalvo.com/)"
            ),
            "Accept": "text/html",
            "Accept-Language": "en",
        },
    )

    for attempt in range(2):
        try:
            with urlopen(
                request,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                if (
                    urlsplit(response.url).hostname
                    != "scholar.google.com"
                ):
                    raise UpdateError(
                        "Scholar redirected away from the public profile."
                    )

                charset = (
                    response.headers.get_content_charset()
                    or "utf-8"
                )

                return response.read().decode(charset)

        except HTTPError as error:
            if error.code < 500 or attempt == 1:
                raise UpdateError(
                    f"Scholar returned HTTP {error.code}; "
                    "no JSON was overwritten."
                ) from error

        except (URLError, TimeoutError, OSError) as error:
            if attempt == 1:
                raise UpdateError(
                    f"Could not reach Scholar: {error}"
                ) from error

        time.sleep(2)

    raise UpdateError("Could not download the Scholar profile.")


def fetch_snapshot():
    records = []
    seen_ids = set()
    profile_metrics = None
    start = 0

    for _ in range(MAX_PAGES):
        page_records, metrics, has_more = parse_page(
            download_page(start)
        )

        if profile_metrics is None:
            profile_metrics = metrics
        elif metrics != profile_metrics:
            raise UpdateError(
                "Profile metrics changed during pagination; "
                "retry on the next run."
            )

        for record in page_records:
            if record["id"] in seen_ids:
                raise UpdateError(
                    "Duplicate pagination results; refusing "
                    "an incomplete snapshot."
                )

            seen_ids.add(record["id"])
            records.append(record)

        if not has_more:
            return records, profile_metrics

        start += len(page_records)
        time.sleep(1)

    raise UpdateError(
        "Pagination limit reached; refusing to save a partial profile."
    )


def normalise_title(value):
    text = unicodedata.normalize(
        "NFKD", str(value or "")
    ).casefold()

    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )

    return " ".join(
        re.findall(
            r"[a-z0-9]+",
            text.replace("&", " and "),
        )
    )


def match_publication(publication, candidates):
    stored_id = publication.get("scholar_publication_id")

    if not stored_id:
        stored_id = parse_qs(
            urlsplit(
                publication.get("scholar_url") or ""
            ).query
        ).get("citation_for_view", [""])[0]

    id_matches = [
        record
        for record in candidates
        if record["id"] == stored_id
    ]

    if len(id_matches) == 1:
        return id_matches[0]

    title = normalise_title(publication.get("title"))

    if not title:
        return None

    exact = [
        record
        for record in candidates
        if normalise_title(record["title"]) == title
    ]

    if len(exact) == 1:
        return exact[0]

    return None


def merge_updates(existing, records, metrics, timestamp):
    publications = existing.get("publications")

    if not isinstance(publications, list) or not publications:
        raise UpdateError(
            "The existing JSON must contain a non-empty "
            "publication list."
        )

    if any(
        not isinstance(publication, dict)
        or not publication.get("title")
        for publication in publications
    ):
        raise UpdateError(
            "Every local publication must be an object with a title."
        )

    if existing.get("scholar_id", SCHOLAR_ID) != SCHOLAR_ID:
        raise UpdateError(
            "The existing JSON belongs to a different Scholar profile."
        )

    if (
        len({record["id"] for record in records})
        != len(records)
    ):
        raise UpdateError(
            "Duplicate Scholar identifiers; refusing "
            "to update citations."
        )

    updated = copy.deepcopy(existing)
    used_ids = set()
    missing = []
    changed = 0

    for publication in updated["publications"]:
        record = match_publication(publication, records)

        if record is None:
            missing.append(
                str(publication.get("title", "Untitled record"))
            )
            continue

        if record["id"] in used_ids:
            raise UpdateError(
                "Two local publications match one Scholar record; "
                "review the duplicates."
            )

        used_ids.add(record["id"])

        changed += (
            publication.get("citations") != record["citations"]
        )

        publication["citations"] = record["citations"]
        publication["citations_updated_at"] = timestamp
        publication["scholar_publication_id"] = record["id"]
        publication["scholar_url"] = record["scholar_url"]

    minimum = math.ceil(
        len(publications) * MIN_MATCH_RATIO
    )

    if len(used_ids) < minimum:
        raise UpdateError(
            f"Only {len(used_ids)}/{len(publications)} "
            f"publications matched; at least {minimum} "
            "are required. The existing JSON will be preserved."
        )

    updated.update({
        "source": "Google Scholar",
        "scholar_id": SCHOLAR_ID,
        "profile_url": PROFILE_URL,
        "updated_at": timestamp,
        "total_publications": len(publications),
        "scholar_total_publications": len(records),
        "metrics": metrics,
    })

    new_records = [
        record
        for record in records
        if record["id"] not in used_ids
    ]

    return updated, changed, missing, new_records


def write_json_atomic(path, data):
    temporary = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)

            json.dump(
                data,
                handle,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )

            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, path)

    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_FILE,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate without modifying the JSON.",
    )

    args = parser.parse_args()

    try:
        existing = json.loads(
            args.file.read_text(encoding="utf-8")
        )

        if not isinstance(existing, dict):
            raise UpdateError(
                "The JSON root must be an object."
            )

        records, metrics = fetch_snapshot()

        timestamp = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
        )

        updated, changed, missing, new_records = merge_updates(
            existing,
            records,
            metrics,
            timestamp,
        )

        if not args.dry_run:
            write_json_atomic(args.file, updated)

        action = "Validated" if args.dry_run else "Saved"

        print(
            f"{action} "
            f"{len(updated['publications'])} curated publications."
        )

        print(
            f"Matched "
            f"{len(updated['publications']) - len(missing)} "
            f"records; {changed} citation counts changed."
        )

        print(
            f"Profile: {metrics['citations']} citations; "
            f"h-index {metrics['h_index']}."
        )

        for title in missing:
            print(
                "Unmatched local record; previous citations "
                f"preserved: {title}"
            )

        for record in new_records:
            print(
                "Scholar record for manual review; "
                f"not added automatically: {record['title']}"
            )

        return 0

    except (UpdateError, OSError, ValueError) as error:
        print(
            f"Update failed: {error}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())
