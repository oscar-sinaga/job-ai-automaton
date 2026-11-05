#!/usr/bin/env python3
"""Rebuild data-only deliverables from immutable YYYY-MM-DD.json archives."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zipfile import ZipFile, ZIP_DEFLATED

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN = 'Belum diketahui'
POLICY = {
    'identity': 'Exact normalized platform + source_job_id; otherwise explicit id, then URL without known tracking parameters; never fuzzy title/company matching.',
    'observations': 'Every listing and exclusion retained verbatim with archive path, zero-based index, run ID and collection date (WIB). Latest listing supplies display fields; exclusions do not erase listing facts.',
    'dates': 'Collection dates are run_date_wib, not posting dates or continuous availability. Date filters match any actual observation, including exclusions.',
    'descriptions': 'Existing archive summaries retained; summary-only is not full text. Optional enrichment adds attributed sections without replacing original records.',
    'availability': 'Historical observations only; visible Apply links do not establish current availability. Separate employer sources and conflicts remain distinct.',
}
TRACKING = {'trk', 'trackingid', 'refid', 'ref', 'tracking', 'fbclid', 'gclid'}


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def stable_id(record, archive, index):
    source = str(record.get('source') or '').strip().lower()
    source_id = record.get('source_job_id')
    if source and source_id is not None and str(source_id).strip():
        return f'{source}:{str(source_id).strip()}'
    if record.get('id'):
        return str(record['id'])
    if record.get('canonical_url'):
        p = urlsplit(record['canonical_url'])
        query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                 if not k.lower().startswith('utm_') and k.lower() not in TRACKING]
        url = urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, urlencode(query), ''))
        return 'url:' + hashlib.sha256(url.encode()).hexdigest()[:24]
    return f'archive:{archive}:{index}'


def validate_url(value):
    p = urlsplit(value)
    if p.scheme not in ('https', 'http') or not p.netloc or p.username or p.password:
        raise ValueError(f'Expected public HTTP(S) source URL: {value!r}')
    return value


def validate_timestamp(item):
    if item.get('observed_at'):
        stamp = datetime.fromisoformat(item['observed_at'].replace('Z', '+00:00'))
        if stamp.utcoffset() is None:
            raise ValueError('observed_at must include timezone')
    elif item.get('observation_window_utc'):
        start, end = [datetime.fromisoformat(t.replace('Z', '+00:00')) for t in item['observation_window_utc'].split('/')]
        if start.utcoffset() is None or end.utcoffset() is None or start > end:
            raise ValueError('Invalid observation window')
    else:
        raise ValueError('Need observed_at or observation_window_utc')


def load_enrichments(root, known_ids):
    path = root / 'enrichment.json'
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    if payload.get('schema_version') != 1 or not isinstance(payload.get('jobs'), dict):
        raise ValueError('enrichment.json needs schema_version=1 and a jobs object')
    excerpt_words = defaultdict(int)
    for job_id, item in payload['jobs'].items():
        if job_id not in known_ids:
            raise ValueError(f'Unknown enrichment job ID: {job_id}')
        validate_url(item['source_url'])
        validate_timestamp(item)
        if item['completeness'] not in ('summary_only', 'partial', 'detailed_paraphrase', 'detailed_paraphrase_of_accessible_description', 'complete_user_supplied', 'sectioned_paraphrase_not_full_text', 'supplemental_matching_platform_paraphrase', 'supplemental_matching_official_paraphrase', 'not_enriched_detail_unavailable'):
            raise ValueError('Unsupported enrichment completeness')
        if item['raw_text_availability'] not in ('not_collected', 'unavailable', 'user_supplied'):
            raise ValueError('Unsupported raw_text_availability')
        if not isinstance(item['sections'], list):
            raise ValueError('sections must be a list')
        for section in item['sections']:
            if not isinstance(section.get('heading'), str) or not isinstance(section.get('text'), str):
                raise ValueError('Each section needs string heading and text')
        if item.get('raw_text') and item['raw_text_availability'] != 'user_supplied':
            raise ValueError('Raw text is accepted only when explicitly user_supplied')
        if item['raw_text_availability'] == 'user_supplied' and not item.get('raw_text'):
            raise ValueError('user_supplied raw text requires raw_text')
        if item['completeness'] == 'complete_user_supplied' and not item.get('raw_text'):
            raise ValueError('complete_user_supplied requires user-supplied raw text')
        for observation in item.get('source_observations', []):
            validate_url(observation['source_url'])
            stamp = datetime.fromisoformat(observation['observed_at'].replace('Z', '+00:00'))
            if stamp.utcoffset() is None or not observation.get('status') or not observation.get('note'):
                raise ValueError('Source observations need timestamp with timezone, status, and note')
        for excerpt in item.get('short_excerpts', []):
            excerpt_words[item['source_url']] += len(excerpt.split())
            if excerpt_words[item['source_url']] > 25:
                raise ValueError('Short excerpts exceed 25 words per source URL')
    return payload['jobs']


def archive_sections(record, date):
    result = []
    # These are editorial categories, not invented original source headings.
    for key, heading in [
        ('description_summary', 'Tugas — ringkasan arsip'),
        ('qualification_notes', 'Kualifikasi dan catatan — arsip'),
        ('experience_text', 'Pengalaman — arsip'),
        ('summary', 'Ringkasan tambahan — arsip'),
        ('official_description_summary', 'Tugas — sumber pemberi kerja'),
        ('official_requirements_summary', 'Persyaratan — sumber pemberi kerja'),
        ('official_evidence_notes', 'Catatan sumber pemberi kerja'),
        ('external_benefits', 'Benefit — tujuan eksternal'),
    ]:
        if record.get(key):
            official = key.startswith('official_')
            url = ((record.get('official_job_url') or record.get('supplemental_official_url'))
                   if official else record.get('external_destination_url') if key.startswith('external_')
                   else record.get('canonical_url'))
            result.append({'heading': heading, 'text': record[key] if isinstance(record[key], str) else dumps(record[key]),
                           'source_url': url or record.get('canonical_url'),
                           'observed_at': (record.get('official_checked_at') or record.get('official_verification_time_window_utc') if official else record.get('checked_at') or record.get('verified_at') or record.get('verification_time_window_utc')),
                           'observation_date_wib': date, 'completeness': 'summary_only', 'origin_field': key})
    return result


def build(root=ROOT):
    runs, grouped, archives = [], defaultdict(list), []
    for path in sorted(root.glob('????-??-??.json')):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}\.json', path.name):
            continue
        daily = json.loads(path.read_text())
        date = daily['run_date_wib']
        if date != path.stem:
            raise ValueError(f'Run date differs from archive filename: {path.name}')
        datetime.strptime(date, '%Y-%m-%d')
        if daily['listing_count'] != len(daily['listings']):
            raise ValueError(f'Incorrect listing_count in {path.name}')
        runs.append({'archive_file': path.name, 'metadata': {k: v for k, v in daily.items() if k not in ('listings', 'excluded')}})
        # CSV/Markdown are projections/annotations, not additional job observations.
        # Hash all archive variants, and link them without altering their contents.
        for variant in sorted(root.glob(path.stem + '.*')):
            archives.append({'path': variant.name, 'sha256': hashlib.sha256(variant.read_bytes()).hexdigest(), 'size_bytes': variant.stat().st_size})
        for kind in ('listings', 'excluded'):
            for index, record in enumerate(daily.get(kind, [])):
                job_id = stable_id(record, path.name, f'{kind}:{index}')
                grouped[job_id].append({'kind': kind, 'run_date_wib': date, 'run_id': daily['run_id'],
                                        'archive_file': path.name, 'record_index': index, 'record': record})
    if not runs:
        raise ValueError('No daily JSON archives found')
    enrichments = load_enrichments(root, grouped)
    jobs = []
    for job_id, observations in sorted(grouped.items()):
        listings = [o for o in observations if o['kind'] == 'listings']
        exclusions = [o for o in observations if o['kind'] == 'excluded']
        display_observation = (listings or observations)[-1]
        record = display_observation['record']
        job = {k: record.get(k) for k in ['title', 'company', 'source', 'source_job_id', 'canonical_url', 'role_family', 'location', 'country', 'employment_type', 'work_arrangement', 'seniority', 'skills', 'availability_status', 'verification_status', 'verification_confidence', 'experience_min_years', 'experience_max_years', 'experience_text', 'salary_currency', 'salary_min', 'salary_max', 'salary_period', 'posted_at', 'posted_relative_text', 'deadline', 'official_job_url', 'supplemental_official_url', 'external_destination_url', 'official_source_status']}
        if not job['title']:
            job['title'] = f'Judul tidak tersimpan ({job_id})'
        job.update({'id': job_id, 'details_anchor': 'job-' + hashlib.sha256(job_id.encode()).hexdigest()[:20],
                    'feed_state': 'recorded_listing' if listings else 'excluded_only',
                    'observation_dates_wib': sorted({o['run_date_wib'] for o in observations}),
                    'observation_count': len(observations), 'listing_observation_count': len(listings),
                    'exclusion_observation_count': len(exclusions), 'display_fields_date_wib': display_observation['run_date_wib'],
                    'latest_exclusion_reason': exclusions[-1]['record'].get('reason') if exclusions else None,
                    'source_cautions': [record[k] for k in ('official_evidence_notes', 'qualification_notes') if record.get(k) and any(word in record[k].lower() for word in ('conflict', 'discrepancy', 'hirer verification'))],
                    'observations': observations})
        job['first_seen_wib'], job['last_seen_wib'] = job['observation_dates_wib'][0], job['observation_dates_wib'][-1]
        links = []
        for obs in observations:
            for key, value in obs['record'].items():
                if (key.endswith('_url') or key in ('canonical_url', 'evidence_url')) and isinstance(value, str) and value.startswith(('https://', 'http://')):
                    link = {'field': key, 'url': value, 'observation_date_wib': obs['run_date_wib']}
                    if link not in links:
                        links.append(link)
        job['source_links'] = links
        sections = []
        for obs in listings:
            sections.extend(archive_sections(obs['record'], obs['run_date_wib']))
        item = enrichments.get(job_id)
        job['description'] = {
            'completeness': item['completeness'] if item and item['sections'] else 'summary_only' if sections else 'unavailable',
            'raw_text_availability': item['raw_text_availability'] if item else 'not_collected',
            'coverage_note': 'Arsip harian hanya menyimpan ringkasan; teks lengkap dan susunan bagian asli tidak dikumpulkan.' if not item or not item['sections'] else 'Detail tambahan beratribusi; data arsip asli tetap disimpan pada observations.',
            'sections': sections,
            'enrichment': item,
        }
        jobs.append(job)
    return {'schema_version': 1, 'dataset': 'Consolidated historical job observations', 'date_timezone': 'Asia/Jakarta',
            'latest_collection_date_wib': runs[-1]['metadata']['run_date_wib'], 'policy': POLICY,
            'counts': {'jobs': len(jobs), 'recorded_listings': sum(j['feed_state'] == 'recorded_listing' for j in jobs),
                       'excluded_only': sum(j['feed_state'] == 'excluded_only' for j in jobs),
                       'observations': sum(j['observation_count'] for j in jobs), 'runs': len(runs)},
            'archives': archives, 'runs': runs, 'jobs': jobs}


def text_value(value):
    if value is None:
        return ''
    return dumps(value) if isinstance(value, (list, dict)) else value


def sheet(wb, name, headers, rows):
    ws = wb.create_sheet(name)
    ws.append(headers)
    for row in rows:
        ws.append([text_value(v) for v in row])
    for row in ws:
        for cell in row:
            if isinstance(cell.value, str):
                if len(cell.value) > 32767:
                    raise ValueError(f'Excel cell would truncate in {name}; chunk text first')
                cell.data_type = 's'  # Keep formula-looking source content literal.
            cell.alignment = Alignment(vertical='top', wrap_text=True)
    ws.freeze_panes = 'A2'
    if ws.max_row > 1:
        table = Table(displayName=name, ref=ws.dimensions)
        table.tableStyleInfo = TableStyleInfo(name='TableStyleMedium2', showRowStripes=True)
        ws.add_table(table)
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='183F49')
    for col in ws.columns:
        heading = col[0].value
        ws.column_dimensions[col[0].column_letter].width = 55 if heading in ('text', 'value', 'title', 'coverage_note', 'reason') else 28
    return ws


def hyperlink(cell, url):
    if url and url.startswith(('http://', 'https://')):
        cell.hyperlink = validate_url(url)
        cell.style = 'Hyperlink'


def chunks(text, size=30000):
    return [text[i:i + size] for i in range(0, len(text), size)] or ['']


def workbook(data, output):
    wb = Workbook()
    wb.remove(wb.active)
    fixed_time = datetime(2000, 1, 1, tzinfo=timezone.utc)
    wb.properties.created = wb.properties.modified = fixed_time
    sheet(wb, 'Readme', ['topic', 'value'], [
        ['Scope', f"Historical archive: {data['counts']['recorded_listings']} listed jobs + {data['counts']['excluded_only']} excluded-only identities. Use Jobs feed_state to distinguish."],
        ['Dates', 'WIB collection dates, not posting dates. Observations has one row per actual dated occurrence; use its exact-date filter.'],
        ['Details', 'Jobs Details links to offline HTML; Descriptions is readable inside Excel. Keep all-jobs.html beside this workbook.'],
        ['Unknowns', 'Blank = unknown, not zero. No claim that Apply links remain open.'],
        ['Raw fields', 'Fields preserves each original observation field as JSON; rejoin numbered chunks before JSON parsing. Runs contains complete run metadata.'],
        ['Enrichment', 'Optional enrichment.json is validated and rendered; see README.md contract.'],
    ] + [[k, v] for k, v in data['policy'].items()])
    headers = ['id', 'details', 'title', 'company', 'feed_state', 'source', 'role_family', 'employment_type', 'work_arrangement', 'location', 'first_seen_wib', 'last_seen_wib', 'observation_dates_wib', 'observation_count', 'availability_status', 'verification_status', 'verification_confidence', 'description_completeness', 'raw_text_availability', 'enrichment_source_notes', 'source_cautions', 'skills', 'experience_min_years', 'experience_max_years', 'experience_text', 'salary_currency', 'salary_min', 'salary_max', 'salary_period', 'posted_at', 'posted_relative_text', 'deadline', 'canonical_url', 'official_job_url', 'supplemental_official_url', 'external_destination_url', 'latest_exclusion_reason']
    rows = []
    for j in data['jobs']:
        flat = dict(j, details='Buka detail', description_completeness=j['description']['completeness'], raw_text_availability=j['description']['raw_text_availability'], enrichment_source_notes=(j['description']['enrichment'] or {}).get('availability_conflict') or (j['description']['enrichment'] or {}).get('source_observations'))
        rows.append([flat.get(k) for k in headers])
    ws = sheet(wb, 'Jobs', headers, rows)
    for rownum, j in enumerate(data['jobs'], 2):
        ws.cell(rownum, 2).hyperlink = f"all-jobs.html#{j['details_anchor']}"
        ws.cell(rownum, 2).style = 'Hyperlink'
        for name in ('canonical_url', 'official_job_url', 'supplemental_official_url', 'external_destination_url'):
            hyperlink(ws.cell(rownum, headers.index(name) + 1), j.get(name))
    obs_rows, field_rows, desc_rows, link_rows = [], [], [], []
    for j in data['jobs']:
        for obs in j['observations']:
            r = obs['record']
            obs_rows.append([j['id'], obs['run_date_wib'], obs['kind'], obs['archive_file'], obs['record_index'], obs['run_id'], r.get('title'), r.get('company'), r.get('role_family'), r.get('employment_type'), r.get('location'), r.get('availability_status'), r.get('verification_status'), r.get('verification_time_window_utc'), r.get('reason'), r.get('canonical_url')])
            for key, value in r.items():
                for part, chunk in enumerate(chunks(dumps(value)), 1):
                    field_rows.append([j['id'], obs['archive_file'], obs['kind'], obs['record_index'], key, part, chunk])
        description = j['description']
        sections = list(description['sections'])
        item = description['enrichment']
        if item:
            sections += [{'heading': 'Provenance / sumber tambahan', 'text': item.get('provenance', ''), 'source_url': item['source_url'], 'observed_at': item.get('observed_at') or item.get('observation_window_utc'), 'completeness': item['completeness']}]
            if item.get('availability_conflict'):
                sections.append({'heading': 'official_closed / konflik sumber', 'text': item['availability_conflict'], 'source_url': item.get('supplemental_official_url'), 'observed_at': item.get('official_observation_window_utc'), 'completeness': item['completeness']})
            sections += [dict(s, source_url=item['source_url'], observed_at=item.get('observed_at') or item.get('observation_window_utc'), completeness=item['completeness']) for s in item['sections']]
            sections += [{'heading': o['status'], 'text': o['note'], 'source_url': o['source_url'], 'observed_at': o['observed_at'], 'completeness': item['completeness']} for o in item.get('source_observations', [])]
            sections += [{'heading': 'Kutipan singkat', 'text': s, 'source_url': item['source_url'], 'observed_at': item.get('observed_at') or item.get('observation_window_utc'), 'completeness': item['completeness']} for s in item.get('short_excerpts', [])]
            if item.get('raw_text'):
                sections.append({'heading': 'Teks mentah dari pengguna', 'text': item['raw_text'], 'source_url': item['source_url'], 'observed_at': item.get('observed_at') or item.get('observation_window_utc'), 'completeness': item['completeness']})
        sections = [{'heading': 'Cakupan deskripsi', 'text': description['coverage_note'], 'completeness': description['completeness']}] + sections
        for section in sections:
            for part, chunk in enumerate(chunks(section['text']), 1):
                desc_rows.append([j['id'], section['heading'], part, chunk, section.get('source_url'), section.get('observed_at'), section.get('observation_date_wib'), section.get('completeness'), description['raw_text_availability']])
        link_rows += [[j['id'], l['field'], l['url'], l['observation_date_wib']] for l in j['source_links']]
        if item:
            if item.get('supplemental_official_url'):
                link_rows.append([j['id'], 'enrichment_supplemental_official_url', item['supplemental_official_url'], item.get('official_observation_window_utc') or item.get('observation_window_utc')])
            link_rows.append([j['id'], 'enrichment_source_url', item['source_url'], item.get('observed_at') or item.get('observation_window_utc')])
            for o in item.get('source_observations', []):
                link_rows.append([j['id'], o['status'], o['source_url'], o['observed_at']])
    ws = sheet(wb, 'Observations', ['id', 'run_date_wib', 'kind', 'archive_file', 'record_index', 'run_id', 'title', 'company', 'role_family', 'employment_type', 'location', 'availability_status', 'verification_status', 'verification_time_window_utc', 'reason', 'canonical_url'], obs_rows)
    for row in ws.iter_rows(min_row=2):
        hyperlink(row[-1], row[-1].value)
    sheet(wb, 'Fields', ['id', 'archive_file', 'kind', 'record_index', 'field', 'part', 'value'], field_rows)
    ws = sheet(wb, 'Descriptions', ['id', 'heading', 'part', 'text', 'source_url', 'observed_at', 'observation_date_wib', 'completeness', 'raw_text_availability'], desc_rows)
    for row in ws.iter_rows(min_row=2):
        hyperlink(row[4], row[4].value)
    ws = sheet(wb, 'Sources', ['id', 'field', 'source_url', 'observation_date_wib'], link_rows)
    for row in ws.iter_rows(min_row=2):
        hyperlink(row[2], row[2].value)
    run_rows = []
    for run in data['runs']:
        for key, value in run['metadata'].items():
            for part, chunk in enumerate(chunks(dumps(value)), 1):
                run_rows.append([run['archive_file'], key, part, chunk])
    enrichment_rows = []
    for j in data['jobs']:
        for key, value in (j['description']['enrichment'] or {}).items():
            for part, chunk in enumerate(chunks(dumps(value)), 1):
                enrichment_rows.append([j['id'], key, part, chunk])
    sheet(wb, 'Enrichment', ['id', 'field', 'part', 'value'], enrichment_rows)
    sheet(wb, 'Runs', ['archive_file', 'field', 'part', 'value'], run_rows)
    ws = sheet(wb, 'Archives', ['path', 'sha256', 'size_bytes'], [[a[k] for k in ('path', 'sha256', 'size_bytes')] for a in data['archives']])
    for row in ws.iter_rows(min_row=2):
        row[0].hyperlink = row[0].value
        row[0].style = 'Hyperlink'
    wb.save(output)
    # XLSX is a ZIP: fixed timestamps make identical inputs produce identical bytes.
    with ZipFile(output) as archive:
        files = [(info, archive.read(info.filename)) for info in archive.infolist()]
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        for info, content in files:
            if info.filename == 'docProps/core.xml':
                content = re.sub(rb'(<dcterms:modified[^>]*>).*?(</dcterms:modified>)', rb'\g<1>2000-01-01T00:00:00Z\g<2>', content)
            info.date_time = (2000, 1, 1, 0, 0, 0)
            archive.writestr(info, content)


def markdown_index(data):
    def escape(value):
        return str(value or 'Belum diketahui').replace('|', r'\|').replace('\n', ' ')
    lines = [f"**{data['counts']['jobs']} identitas · {data['counts']['recorded_listings']} pernah masuk daftar · {data['counts']['excluded_only']} hanya dikecualikan · {data['counts']['observations']} pengamatan · {data['counts']['runs']} run.** Pengumpulan terakhir: {data['latest_collection_date_wib']} WIB.", '',
             '| Posisi | Perusahaan | Bidang | Tanggal pengamatan WIB | Cakupan | Detail |',
             '|---|---|---|---|---|---|']
    for job in data['jobs']:
        title = escape(job['title']).replace('[', r'\[').replace(']', r'\]')
        url = job.get('canonical_url')
        title = f'[{title}]({url})' if url else title
        lines.append('| ' + ' | '.join([title, escape(job['company']), escape(job['role_family']), ', '.join(job['observation_dates_wib']), job['feed_state'], f"[Buka](all-jobs.html#{job['details_anchor']})"]) + ' |')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT)
    args = parser.parse_args()
    data = build()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'all-jobs.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    template = (ROOT / 'tools' / 'viewer.html').read_text()
    embedded = dumps(data).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    (args.output_dir / 'all-jobs.html').write_text(template.replace('__DATA_JSON__', embedded))
    workbook(data, args.output_dir / 'all-jobs.xlsx')
    readme = (ROOT / 'README.md').read_text()
    readme = re.sub(r'(?s)(<!-- GENERATED_INDEX_START -->).*?(<!-- GENERATED_INDEX_END -->)', lambda m: m[1] + '\n' + markdown_index(data) + '\n' + m[2], readme)
    (args.output_dir / 'README.md').write_text(readme)
    print(json.dumps(data['counts']))


if __name__ == '__main__':
    main()
