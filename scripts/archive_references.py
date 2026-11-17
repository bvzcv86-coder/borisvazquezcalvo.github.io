"""Generate individual references and full-archive downloads."""
import json
from pathlib import Path

from build_publication_pages import absolute, bib_escape, bibtex, ris

ROOT = Path(__file__).resolve().parent.parent


def archive_entry(publication, reference):
    """Export structured bibliography fields for works without a dedicated research page."""
    kind = reference['type']
    ris_type = {'article': 'JOUR', 'incollection': 'CHAP', 'book': 'BOOK',
                'phdthesis': 'THES', 'techreport': 'RPRT'}[kind]
    title = publication['title']
    year = publication['year']
    url = 'https://doi.org/' + publication['doi'] if publication.get('doi') else publication['scholar_url']
    fields = {'title': '{' + bib_escape(title) + '}', 'year': year}
    lines = [('TY', ris_type), ('TI', title), ('PY', year)]
    for field, tag in [('author', 'AU'), ('editor', 'ED')]:
        if field in reference:
            people = reference[field]
            lines.extend((tag, name) for name in people)
            fields[field] = ' and '.join(bib_escape(name) for name in people)
    for field, tag in [('journal', 'JO'), ('booktitle', 'T2'), ('volume', 'VL'), ('number', 'IS'),
                       ('publisher', 'PB'), ('school', 'PB'), ('institution', 'PB'), ('series', 'T3'),
                       ('note', 'N1')]:
        if field in reference:
            value = reference[field]
            lines.append((tag, value))
            fields[field] = bib_escape(value)
    if kind == 'phdthesis':
        lines.append(('M3', 'Doctoral dissertation'))
    if reference.get('pages'):
        pages = reference['pages'].split('-', 1)
        fields['pages'] = '--'.join(pages)
        lines.append(('SP', pages[0]))
        if len(pages) == 2:
            lines.append(('EP', pages[1]))
    if publication.get('doi'):
        fields['doi'] = publication['doi']
        lines.append(('DO', fields['doi']))
    fields['url'] = url
    lines.append(('UR', url))
    if publication.get('eprint_url'):
        lines.append(('L1', absolute(publication['eprint_url'])))
    lines.append(('ER', ''))
    ris_text = ''.join(f'{tag}  - {value}\n' for tag, value in lines) + '\n'
    bib_fields = ',\n'.join(f'  {key} = {{{value}}}' for key, value in fields.items())
    bib_text = f"@{kind}{{{reference['slug']},\n{bib_fields}\n}}\n"
    return ris_text, bib_text


def write_references(publications):
    definitions = json.loads((ROOT / 'publication-pages.json').read_text())['publications']
    curated = {d['id']: d for d in definitions}
    directory = ROOT / 'files/references'
    directory.mkdir(parents=True, exist_ok=True)
    slugs = {}
    exports = {'ris': [], 'bib': []}
    for publication in publications:
        identifier = publication['scholar_publication_id']
        if identifier in curated:
            reference = curated[identifier]
            entries = ris(publication, reference), bibtex(publication, reference)
        else:
            reference = publication['reference']
            entries = archive_entry(publication, reference)
        slug = reference['slug']
        if identifier in slugs or slug in slugs.values():
            raise ValueError(f'Duplicate reference: {slug}')
        slugs[identifier] = slug
        for extension, entry in zip(('ris', 'bib'), entries):
            (directory / f'{slug}.{extension}').write_text(entry, encoding='utf-8')
            exports[extension].append(entry)
    for extension, entries in exports.items():
        separator = '\n' if extension == 'bib' else ''
        (directory / f'all-publications.{extension}').write_text(separator.join(entries), encoding='utf-8')
    return slugs
