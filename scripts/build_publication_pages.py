#!/usr/bin/env python3
"""Build curated research pages and portable references without a web framework.

publication-pages.json holds editorial summaries and verified access information.
publications.json remains the source for bibliographic records and citation counts.
Run this script after updating either file; it never infers a full-text PDF URL.
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = 'https://borisvazquezcalvo.com'
GROUPS = {
    'Fan translation and gaming': '/topics/fan-translation-language-education/',
    'Informal learning and social media': '/topics/informal-digital-language-learning/',
    'Critical digital literacies': '/topics/digital-literacies-language-education/',
    'Language education and teaching': '/topics/language-teacher-education/',
}

def esc(value):
    return html.escape(str(value), quote=True)

def absolute(url):
    return SITE + url if url.startswith('/') else url

def link(url, label, classes='', download=False):
    attrs = ' target="_blank" rel="noopener"' if url.startswith('https://') else ''
    if download:
        attrs += ' download'
    return f'<a href="{esc(url)}" class="{esc(classes)}"{attrs}>{label}</a>'

def full_name(person):
    return (person['given'] + ' ' + person['family']).strip()

def initials(given):
    return ' '.join('-'.join(part[0] + '.' for part in token.split('-') if part) for token in given.split())

def citation_names(people, editors=False):
    values = [(initials(p['given']) + ' ' + p['family']) if editors else
              (p['family'] + ', ' + initials(p['given'])) for p in people]
    if len(values) < 2:
        return ''.join(values)
    if len(values) == 2:
        return ' & '.join(values)
    return ', '.join(values[:-1]) + ', & ' + values[-1]

def citation(p, d, formatted=False):
    it = (lambda s: '<em>' + esc(s) + '</em>') if formatted else (lambda s: s)
    plain = esc if formatted else (lambda s: s)
    start = plain(citation_names(d['creators']) + f" ({p['year']}). {p['title']}. ")
    pages = d.get('pages', '').replace('-', '–')
    if d['kind'] == 'chapter':
        editors = citation_names(d['editors'], editors=True)
        middle = plain(f'In {editors} (Eds.), ') + it(d['book']) + plain(f' (pp. {pages}). {d["publisher"]}. ')
    else:
        middle = it(d['journal'] + (', ' + d['volume'] if d['volume'] else ''))
        if d['issue']:
            middle += plain('(' + d['issue'].replace('-', '–') + ')')
        if d.get('article_number'):
            middle += plain(', Article ' + d['article_number'])
        elif pages:
            middle += plain(', ' + pages)
        middle += '. '
    doi = 'https://doi.org/' + p['doi']
    return start + middle + (link(doi, esc(doi)) if formatted else doi)

def ris(p, d):
    lines = ['TY  - ' + ('CHAP' if d['kind'] == 'chapter' else 'JOUR'), 'TI  - ' + p['title']]
    lines.extend('AU  - ' + a['family'] + ', ' + a['given'] for a in d['creators'])
    lines += ['PY  - ' + str(p['year']), 'DO  - ' + p['doi'], 'UR  - https://doi.org/' + p['doi'], 'LA  - ' + d['language']]
    if d['kind'] == 'chapter':
        lines += ['T2  - ' + d['book'], 'PB  - ' + d['publisher']]
        lines.extend('A2  - ' + a['family'] + ', ' + a['given'] for a in d['editors'])
    else:
        lines += ['JO  - ' + d['journal']]
        if d['volume']: lines += ['VL  - ' + d['volume']]
        if d['issue']: lines += ['IS  - ' + d['issue']]
    if d['pages']:
        pages = d['pages'].split('-', 1)
        lines += ['SP  - ' + pages[0]]
        if len(pages) == 2: lines += ['EP  - ' + pages[1]]
    elif d.get('article_number'):
        lines += ['SP  - ' + d['article_number']]
    if d.get('pdf'):
        lines += ['L1  - ' + absolute(d['pdf'])]
    lines += ['ER  - ', '']
    return '\n'.join(lines) + '\n'

def bib_escape(value):
    return str(value).replace('\\', '\\textbackslash{}').replace('&', '\\&').replace('%', '\\%').replace('_', '\\_').replace('#', '\\#')

def bibtex(p, d):
    fields = {'title': '{' + bib_escape(p['title']) + '}',
              'author': ' and '.join(bib_escape(a['family'] + ', ' + a['given']) for a in d['creators']),
              'year': p['year'], 'doi': p['doi'], 'url': 'https://doi.org/' + p['doi']}
    if d['kind'] == 'chapter':
        fields.update(booktitle=bib_escape(d['book']), publisher=bib_escape(d['publisher']),
                      editor=' and '.join(bib_escape(a['family'] + ', ' + a['given']) for a in d['editors']))
    else:
        fields.update(journal=bib_escape(d['journal']))
        if d['volume']: fields['volume'] = d['volume']
        if d['issue']: fields['number'] = d['issue']
    if d['pages']: fields['pages'] = d['pages'].replace('-', '--')
    elif d.get('article_number'): fields['pages'] = d['article_number']
    if d.get('pdf'): fields['file'] = absolute(d['pdf'])
    typ = 'incollection' if d['kind'] == 'chapter' else 'article'
    return f"@{typ}{{{d['slug']},\n" + ',\n'.join(f'  {k} = {{{v}}}' for k, v in fields.items()) + '\n}\n'

def scholarly_head(p, d, url):
    tags = {'citation_title': p['title'], 'citation_publication_date': str(p['year']), 'citation_doi': p['doi'],
            'citation_language': d['language']}
    if d['kind'] == 'chapter':
        tags.update(citation_book_title=d['book'], citation_publisher=d['publisher'])
    else:
        tags.update(citation_journal_title=d['journal'])
        if d['volume']: tags['citation_volume'] = d['volume']
        if d['issue']: tags['citation_issue'] = d['issue']
    if d['pages']:
        parts = d['pages'].split('-', 1)
        tags['citation_firstpage'] = parts[0]
        if len(parts) == 2: tags['citation_lastpage'] = parts[1]
    elif d.get('article_number'):
        tags['citation_firstpage'] = d['article_number']
    if d.get('pdf'): tags['citation_pdf_url'] = absolute(d['pdf'])
    head = '\n'.join(f'<meta name="{k}" content="{esc(v)}" />' for k,v in tags.items())
    head += '\n' + '\n'.join(f'<meta name="citation_author" content="{esc(full_name(a))}" />' for a in d['creators'])
    schema = {'@context':'https://schema.org', '@type':'Chapter' if d['kind'] == 'chapter' else 'ScholarlyArticle',
              '@id':url+'#publication', 'name':p['title'], 'headline':p['title'], 'url':url,
              'identifier':{'@type':'PropertyValue','propertyID':'DOI','value':p['doi']},
              'sameAs':'https://doi.org/'+p['doi'], 'datePublished':str(p['year']), 'inLanguage':d['language'],
              'author':[{'@type':'Person','name':full_name(a), **({'@id':SITE+'/#person'} if 'Boris' in a['given'] else {})} for a in d['creators']]}
    if d['kind'] == 'chapter':
        schema['isPartOf'] = {'@type':'Book', 'name':d['book'], 'publisher':{'@type':'Organization','name':d['publisher']},
                              'editor':[{'@type':'Person','name':full_name(a)} for a in d['editors']]}
    else:
        periodical = {'@type':'Periodical','name':d['journal']}
        parent = {'@type':'PublicationVolume','volumeNumber':d['volume'],'isPartOf':periodical} if d['volume'] else periodical
        schema['isPartOf'] = {'@type':'PublicationIssue','issueNumber':d['issue'],'isPartOf':parent} if d['issue'] else parent
    if d['pages']:
        parts = d['pages'].split('-', 1)
        schema['pageStart'] = parts[0]
        if len(parts) == 2: schema['pageEnd'] = parts[1]
    if d.get('pdf'):
        schema['isAccessibleForFree'] = True
        schema['encoding'] = {'@type':'MediaObject','contentUrl':absolute(d['pdf']),'encodingFormat':'application/pdf'}
        schema['license'] = d['license_url']
    crumb = {'@context':'https://schema.org','@type':'BreadcrumbList','itemListElement':[
        {'@type':'ListItem','position':i,'name':name,'item':address} for i,(name,address) in enumerate([
        ('Home',SITE+'/'),('Publications',SITE+'/publications/'),(d['short_title'],url)],1)]}
    for obj in [schema, crumb]:
        head += '\n<script type="application/ld+json">' + json.dumps(obj,ensure_ascii=False,indent=2).replace('</','<\\/') + '</script>'
    return head

def page(p, d, definitions, by_id, header, footer):
    route = p['page_url']; url = SITE + route
    title = d['short_title'] + ' | Boris Vázquez-Calvo'
    header = re.sub(r' aria-current="page"', '', header)
    header = header.replace(f'href="{route}"', f'href="{route}" aria-current="page"')
    authors = ', '.join(full_name(a) for a in d['creators'])
    doi = 'https://doi.org/' + p['doi']
    export = '/files/references/' + d['slug']
    read = link(d.get('pdf') or d.get('repository') or doi,
                'Open PDF' if d.get('pdf') else ('Read repository copy' if d.get('repository') else 'Read at publisher'), 'button primary')
    if d.get('pdf'):
        read += link(d['pdf'], 'Download PDF', 'button', download=True)
    elif d.get('remote_pdf'):
        read += link(d['remote_pdf'], 'Open repository PDF', 'button')
    read += link(doi, 'Publisher / DOI', 'text-action')
    preview = ''
    if d.get('pdf'):
        preview = f'''<details class="pdf-preview"><summary>Preview the PDF{(' · '+esc(d['pdf_language'])) if d.get('pdf_language') else ''}</summary>
        <p>Read here, or use the PDF links above to open and save the file.</p>
        <div class="pdf-frame" data-pdf-src="{esc(d['pdf'])}" data-pdf-title="{esc(p['title'])}"></div>
        <noscript><p>{link(d['pdf'], 'Open the PDF in your browser')}</p></noscript></details>'''
    access = '<p class="access-note">' + esc(d.get('access_note', '')) + '</p>' if d.get('access_note') else ''
    if d.get('pdf'):
        access += f'<p class="access-note">Full text: {link(d["pdf_source"], "original source")} · {link(d["license_url"], esc(d["license"]))}. Unchanged copy; credit the authors and original publication.</p>'
    related = [x for x in definitions if x['id'] != d['id'] and x['group'] == d['group']][:3]
    related_html = ''.join(f'<li>{link(by_id[x["id"]]["page_url"], esc(x["short_title"]))} <span>({by_id[x["id"]]["year"]})</span></li>' for x in related)
    date_note = ''
    if d.get('online_date') and d['online_date'][:4] != str(p['year']):
        date_note = f'<p class="access-note">First published online {esc(d["online_date"])}; the citation uses the final issue year, {esc(p["year"])}.</p>'
    subtitle = f'<p class="alternate-title">English title: {esc(d["alternate_title"])}</p>' if d.get('alternate_title') else ''
    venue = d['book'] if d['kind']=='chapter' else d['journal']
    return f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8" /><meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{esc(title)}</title><meta name="description" content="{esc(d['summary'])}" />
<meta name="author" content="Boris Vázquez-Calvo" />
<link rel="canonical" href="{url}" /><link rel="icon" href="/favicon.svg?v=1" type="image/svg+xml" />
<meta name="theme-color" content="#111827" />
<meta property="og:title" content="{esc(title)}" /><meta property="og:description" content="{esc(d['summary'])}" />
<meta property="og:type" content="article" /><meta property="og:url" content="{url}" />
<meta property="og:image" content="{SITE}/assets/profile.jpg" /><meta name="twitter:card" content="summary" />
<link rel="stylesheet" href="/assets/styles/layout-d90be46cfc81.css" />
<link rel="stylesheet" href="/assets/site.css?v=20261007p1" />
<link rel="stylesheet" href="/assets/publication-pages.css?v=20261007" />
{scholarly_head(p,d,url)}
</head><body class="research-paper"><a class="skip-link" href="#main-content">Skip to content</a>{header}
<main id="main-content">
<div class="container"><nav class="breadcrumbs" aria-label="Breadcrumb"><ol><li><a href="/">Home</a></li><li><a href="/publications/">Publications</a></li><li><span aria-current="page">{esc(d['short_title'])}</span></li></ol></nav></div>
<section class="hero"><div class="container">
<span class="eyebrow">{'Book chapter' if d['kind']=='chapter' else 'Journal article'} · {p['year']} · {esc(d['group'])}</span>
<h1{' lang="es"' if d['language']=='es' else ''}>{esc(p['title'])}</h1>{subtitle}
<p class="paper-authors">{esc(authors)}</p><p class="paper-venue">{esc(venue)} · {p['year']}</p>
<p class="subtitle">{esc(d['summary'])}</p></div></section>
<div class="container paper-layout">
<aside class="read-panel" aria-labelledby="read-title"><h2 id="read-title">Read, save and cite</h2>
<p>Save this paper for reading and citing later.</p><div class="read-actions">{read}</div>
<div class="reference-actions">{link(export+'.ris','Save reference (RIS)','button',True)}{link(export+'.bib','BibTeX','button',True)}</div>
<p class="reference-help">Use Zotero Connector or Mendeley Web Importer to save this page, or import the RIS file into your reference manager.</p>{access}</aside>
<article class="paper-content"><section><h2>{'Approach' if d['kind']=='chapter' else 'Study and methods'}</h2><p>{esc(d['method'])}</p></section>
<section><h2>{'Main ideas' if d['kind']=='chapter' else 'Key findings'}</h2><ul>{''.join('<li>'+esc(f)+'</li>' for f in d['findings'])}</ul><p class="scope-note">{esc(d['scope'])}</p></section>
<section><h2>How this work can be used</h2><p>{esc(d['use'])}</p></section>
<section class="citation-section" id="cite"><h2>Cite this {'chapter' if d['kind']=='chapter' else 'article'}</h2>
<p class="formatted-citation">{citation(p,d,True)}</p>{date_note}
<button class="button copy-citation" type="button" data-citation="citation-text" hidden>Copy citation</button>
<p class="copy-status" role="status" aria-live="polite"></p>
<label class="citation-fallback" for="citation-text" hidden>Select and copy this citation:</label>
<textarea id="citation-text" class="citation-fallback" readonly hidden>{esc(citation(p,d))}</textarea>
</section>{preview}
<section class="related-papers"><h2>Related research</h2><ul>{related_html}</ul>
<p>{link(GROUPS[d['group']], esc(d['group']))} · {link('/materials/', 'Teaching and open materials')} · {link('/publications/','More publications')}</p></section>
<p class="verification-note">Publication details and access links checked {d['verified_at']}. {link(d['source'] or doi, 'Source record')}.</p>
</article></div></main>{footer}
<script src="/assets/site.js?v=20261007p1" defer></script>
<script src="/assets/publication-pages.js?v=20261007" defer></script>
</body></html>\n'''

def publication_menu(definitions, by_id, route):
    entries = []
    for d in sorted(definitions, key=lambda d:by_id[d['id']]['year'], reverse=True):
        p = by_id[d['id']]
        current = ' aria-current="page"' if p['page_url']==route else ''
        entries.append(f'<a href="{p["page_url"]}"{current}><span>{esc(d["short_title"])} <span class="pub-nav-year">({p["year"]})</span></span></a>')
    current = ' aria-current="page"' if route=='/publications/' else ''
    all_link = f'<a class="pub-nav-all" href="/publications/"{current}>All publications</a>'
    desktop = '<details class="nav-item"><summary>Publications</summary><div class="dropdown-menu publications-menu">'+all_link+''.join(entries)+'</div></details>'
    mobile = '<details class="mobile-publications"><summary>Publications</summary><div class="mobile-publication-links">'+all_link+''.join(entries)+'</div></details>'
    return desktop, mobile

def main():
    data = json.loads((ROOT/'publications.json').read_text())
    definitions = json.loads((ROOT/'publication-pages.json').read_text())['publications']
    by_id = {p['scholar_publication_id']:p for p in data['publications']}
    template = (ROOT/'publications/memes-and-identity-language-teacher-education/index.html').read_text()
    header = re.search(r'<header>.*?</header>',template,re.S)[0]
    footer = re.search(r'<footer.*?</footer>',template,re.S)[0]
    refs = ROOT/'files/references'; refs.mkdir(exist_ok=True)
    selected_ris = []; selected_bib = []
    for d in definitions:
        p = by_id[d['id']]
        assert d['creators'] and p['doi'], d['slug']
        route = ROOT/p['page_url'].lstrip('/'); route.mkdir(parents=True,exist_ok=True)
        (route/'index.html').write_text(page(p,d,definitions,by_id,header,footer))
        (refs/(d['slug']+'.ris')).write_text(ris(p,d))
        (refs/(d['slug']+'.bib')).write_text(bibtex(p,d))
        if d['selected']:
            selected_ris.append(ris(p,d)); selected_bib.append(bibtex(p,d))
    (refs/'selected-publications.ris').write_text(''.join(selected_ris))
    (refs/'selected-publications.bib').write_text('\n'.join(selected_bib))
    path = ROOT/'publications/index.html'
    source = path.read_text()
    source = re.sub(r'<section id="featured">.*?</section>','',source,flags=re.S)
    source = re.sub(r'<a class="button primary" href="#featured">.*?</a>\s*','',source)
    # Keep portable collection downloads as a small archive tool, without a showcase.
    exports = '<div class="buttons collection-downloads">'+link('/files/references/selected-publications.ris','Save research collection (RIS)','button',True)+link('/files/references/selected-publications.bib','Research collection (BibTeX)','button',True)+'</div>'
    source = re.sub(r'<div class="buttons collection-downloads">.*?</div>','',source,flags=re.S)
    source = source.replace('<!-- PUBLICATIONS:START -->',exports+'\n<!-- PUBLICATIONS:START -->')
    path.write_text(source)
    for path in ROOT.rglob('*.html'):
        source = path.read_text()
        route = '/'+str(path.relative_to(ROOT)).removesuffix('index.html') if path!=ROOT/'index.html' else '/'
        desktop,mobile = publication_menu(definitions,by_id,route)
        source = re.sub(r'<details class="nav-item"><summary>Publications</summary>.*?</details>',lambda _:desktop,source,flags=re.S)
        source = re.sub(r'<details class="mobile-publications">.*?</details>',lambda _:mobile,source,flags=re.S)
        # Existing mobile menus use a single Publications link.
        source = re.sub(r'(<div class="mobile-links">.*?)(<a href="/publications/"(?: aria-current="page")?>Publications</a>)',lambda m:m[1]+mobile,source,flags=re.S)
        source = source.replace('/publications/#featured','/publications/').replace('Read, save and cite selected research','Read, save and cite research')
        path.write_text(source)
    print('Built 16 publication pages and 34 reference files (15 selected works + recent AI article).')

if __name__ == '__main__':
    main()
