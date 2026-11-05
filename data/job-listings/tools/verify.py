#!/usr/bin/env python3
"""Verify archive coverage, lossless Excel/JSON, regeneration and real browser UI."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook
from playwright.sync_api import sync_playwright, expect

import regenerate as generator

ROOT = generator.ROOT


def reconstruct(ws, key_columns, part_column, value_column):
    fields = defaultdict(list)
    for row in ws.iter_rows(min_row=2, values_only=True):
        fields[tuple(row[i] for i in key_columns)].append((row[part_column], row[value_column]))
    return {key: json.loads(''.join(value or '' for _, value in sorted(parts))) for key, parts in fields.items()}


def verify_data(data):
    assert json.loads(json.dumps(data, ensure_ascii=False)) == data
    expected_observations = {}
    expected_runs = {}
    for path in sorted(ROOT.glob('????-??-??.json')):
        daily = json.loads(path.read_text())
        expected_runs[path.name] = {k: v for k, v in daily.items() if k not in ('listings', 'excluded')}
        for kind in ('listings', 'excluded'):
            for index, record in enumerate(daily.get(kind, [])):
                expected_observations[(path.name, kind, index)] = record
    actual_observations = {}
    for job in data['jobs']:
        dates = []
        for obs in job['observations']:
            key = obs['archive_file'], obs['kind'], obs['record_index']
            assert key not in actual_observations, key
            assert generator.stable_id(obs['record'], obs['archive_file'], f"{obs['kind']}:{obs['record_index']}") == job['id']
            actual_observations[key] = obs['record']
            dates.append(obs['run_date_wib'])
        assert job['observation_dates_wib'] == sorted(set(dates))
        assert job['observation_count'] == len(job['observations'])
    assert actual_observations == expected_observations, 'Archive observation lost/changed'
    assert {r['archive_file']: r['metadata'] for r in data['runs']} == expected_runs
    assert len({j['id'] for j in data['jobs']}) == data['counts']['jobs']
    assert len(expected_observations) == data['counts']['observations']
    for entry in data['archives']:
        assert hashlib.sha256((ROOT / entry['path']).read_bytes()).hexdigest() == entry['sha256']
    embedded = re.search(r'<script id="dataset" type="application/json">(.*?)</script>', (ROOT / 'all-jobs.html').read_text(), re.S)
    assert json.loads(embedded[1]) == data, 'HTML embedded dataset differs from JSON'
    assert data == generator.build(), 'Generated JSON is stale'
    assert all(f"all-jobs.html#{j['details_anchor']}" in (ROOT / 'README.md').read_text() for j in data['jobs'])
    wb = load_workbook(ROOT / 'all-jobs.xlsx')
    for ws in wb:
        assert ws.freeze_panes == 'A2'
        if ws.max_row > 1:
            assert len(ws.tables) == 1, ws.title
            table = next(iter(ws.tables.values()))
            assert table.ref == ws.dimensions and table.autoFilter.ref == ws.dimensions
        assert not any(cell.data_type == 'f' for row in ws for cell in row), 'Unexpected formula'
    fields = reconstruct(wb['Fields'], [1, 2, 3, 4], 5, 6)
    for (archive, kind, index), record in expected_observations.items():
        assert {k[3]: value for k, value in fields.items() if k[:3] == (archive, kind, index)} == record
    runs = reconstruct(wb['Runs'], [0, 1], 2, 3)
    for archive, metadata in expected_runs.items():
        assert {k[1]: value for k, value in runs.items() if k[0] == archive} == metadata
    enrichments = reconstruct(wb['Enrichment'], [0, 1], 2, 3)
    expected_enrichment = generator.load_enrichments(ROOT, {j['id'] for j in data['jobs']})
    for job_id, item in expected_enrichment.items():
        assert {k[1]: v for k, v in enrichments.items() if k[0] == job_id} == item
    ws = wb['Jobs']
    headers = [c.value for c in ws[1]]
    assert ws.max_row - 1 == len(data['jobs'])
    for rownum, job in enumerate(data['jobs'], 2):
        assert ws.cell(rownum, 1).value == job['id']
        assert ws.cell(rownum, 2).hyperlink.target == f"all-jobs.html#{job['details_anchor']}"
        for field in ('canonical_url', 'official_job_url', 'supplemental_official_url', 'external_destination_url'):
            cell = ws.cell(rownum, headers.index(field) + 1)
            if job.get(field):
                assert cell.value == cell.hyperlink.target == job[field]
        for field in ('salary_min', 'salary_max', 'experience_min_years', 'experience_max_years'):
            assert ws.cell(rownum, headers.index(field) + 1).value == job[field]
    assert wb['Observations'].max_row - 1 == len(expected_observations)
    for row in wb['Sources'].iter_rows(min_row=2):
        assert row[2].hyperlink.target == row[2].value
    for row in wb['Descriptions'].iter_rows(min_row=2):
        if row[4].value:
            assert row[4].hyperlink.target == row[4].value
    with tempfile.TemporaryDirectory(prefix='job-regeneration-') as tmp:
        subprocess.run([sys.executable, str(ROOT / 'tools/regenerate.py'), '--output-dir', tmp], check=True, capture_output=True)
        for name in ('all-jobs.json', 'all-jobs.html', 'all-jobs.xlsx', 'README.md'):
            assert (ROOT / name).read_bytes() == (Path(tmp) / name).read_bytes(), f'Non-deterministic/stale output: {name}'
    print(f"PASS: {len(data['jobs'])} identities, {len(expected_observations)} original observations, {len(data['archives'])} archive hashes; JSON/HTML/Excel round trips, table filters/links, reproducible outputs")


def verify_future_updates():
    with tempfile.TemporaryDirectory(prefix='job-fixture-') as tmp:
        root = Path(tmp)
        first = {'id': 'jobstreet:1', 'source': 'jobstreet', 'source_job_id': '1', 'title': 'Same title', 'company': 'A', 'canonical_url': 'https://example.org/job/1', 'description_summary': 'Old fact', 'salary_min': None}
        different = dict(first, id='jobstreet:2', source_job_id='2')
        updated = dict(first, description_summary='Changed fact', salary_min=0)
        for date, rows, excluded in [('2026-01-01', [first, different], []), ('2026-01-03', [updated], [dict(first, reason='Duplicate, not closed')])]:
            (root / f'{date}.json').write_text(json.dumps({'run_date_wib': date, 'run_id': date, 'listing_count': len(rows), 'listings': rows, 'excluded': excluded}))
        payload = {'schema_version': 1, 'jobs': {'jobstreet:1': {'source_url': 'https://example.org/job/1', 'observed_at': '2026-01-03T00:00:00Z', 'completeness': 'complete_user_supplied', 'raw_text_availability': 'user_supplied', 'sections': [{'heading': 'Requirements', 'text': '=literal text, not an Excel formula'}], 'raw_text': 'User text\n' * 5000 + '</script><script>throw new Error("unsafe")</script>'}}}
        (root / 'enrichment.json').write_text(json.dumps(payload))
        data = generator.build(root)
        assert len(data['jobs']) == 2, 'Fuzzy dedupe must not merge matching titles'
        job = next(j for j in data['jobs'] if j['id'] == 'jobstreet:1')
        assert len(job['observations']) == 3
        assert job['salary_min'] == 0 and job['observations'][0]['record']['salary_min'] is None
        assert job['observation_dates_wib'] == ['2026-01-01', '2026-01-03']
        assert job['description']['enrichment']['raw_text'] == payload['jobs']['jobstreet:1']['raw_text']
        generator.workbook(data, root / 'test.xlsx')
        wb = load_workbook(root / 'test.xlsx')
        raw = [row for row in wb['Descriptions'].iter_rows(min_row=2, values_only=True) if row[1] == 'Teks mentah dari pengguna']
        assert len(raw) > 1
        assert ''.join(row[3] for row in sorted(raw, key=lambda r: r[2])) == payload['jobs']['jobstreet:1']['raw_text']
        assert not any(c.data_type == 'f' for ws in wb for row in ws for c in row)
        for change in [dict(raw_text_availability='not_collected'), dict(observed_at='2026-01-03T00:00:00'), dict(short_excerpts=['word ' * 26])]:
            bad = copy.deepcopy(payload)
            bad['jobs']['jobstreet:1'].update(change)
            (root / 'enrichment.json').write_text(json.dumps(bad))
            try:
                generator.build(root)
            except ValueError:
                pass
            else:
                raise AssertionError(f'Invalid enrichment accepted: {change}')
    print('PASS: future updates preserve dated versions, distinguish null/zero, avoid fuzzy merges, validate enrichment, chunk long user text, keep formula-like text literal')


def verify_browser(data):
    with sync_playwright() as pw:
        executable = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
        browser = pw.chromium.launch(executable_path=executable, headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1280, 'height': 950})
        errors, network = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: network.append(request.url) if request.url.startswith(('https://', 'http://')) else None)
        page.set_content((ROOT / 'all-jobs.html').read_text())
        def actual_ids():
            return page.locator('#results > .job').evaluate_all('(elements)=>elements.map(e=>e.dataset.jobId).sort()')
        def reset():
            page.locator('#reset').click()
        assert len(actual_ids()) == len(data['jobs'])
        # Exercise every option of every dropdown, checking actual DOM results against source records.
        for selector, key in [('role','role_family'),('source','source'),('employment','employment_type'),('arrangement','work_arrangement'),('location','location'),('feed','feed_state'),('coverage',None)]:
            values = page.locator(f'#{selector} option').evaluate_all('(els)=>els.map(e=>e.value).filter(Boolean)')
            for value in values:
                page.select_option('#' + selector, value)
                expected = [j['id'] for j in data['jobs'] if (j['description']['completeness'] if key is None else j[key] or '__unknown__') == value]
                assert actual_ids() == sorted(expected), (selector, value)
            reset()
        for date in sorted({d for j in data['jobs'] for d in j['observation_dates_wib']}):
            page.fill('#date-from', date)
            page.fill('#date-to', date)
            assert actual_ids() == sorted(j['id'] for j in data['jobs'] if date in j['observation_dates_wib'])
            reset()
        for query in ['Python RAG', 'idempotency', 'no longer', 'GrabFlex', 'no-match-zzzzzz']:
            page.fill('#search', query)
            expected = [j['id'] for j in data['jobs'] if all(t in generator.dumps(j).lower() for t in query.lower().split())]
            assert actual_ids() == sorted(expected), query
            if not expected:
                expect(page.locator('#empty')).to_be_visible()
            reset()
        page.fill('#search', 'Python')
        page.select_option('#source', 'linkedin')
        page.select_option('#role', 'data_engineer')
        page.fill('#date-from', '2026-11-05')
        assert actual_ids() == sorted(j['id'] for j in data['jobs'] if j['source']=='linkedin' and j['role_family']=='data_engineer' and 'Python'.lower() in generator.dumps(j).lower() and any(d >= '2026-11-05' for d in j['observation_dates_wib']))
        reset()
        page.fill('#date-from', '2027-01-01')
        page.fill('#date-to', '2026-01-01')
        expect(page.locator('#date-error')).to_be_visible()
        assert actual_ids() == []
        reset()
        page.select_option('#sort', 'title')
        titles = page.locator('#results > .job h2').all_text_contents()
        assert titles == page.evaluate('(titles)=>[...titles].sort((a,b)=>a.localeCompare(b))', titles)
        reset()
        for job in data['jobs']:
            card = page.locator(f"#{job['details_anchor']}")
            card.locator(':scope > summary').click()
            expect(card.locator('.detail')).not_to_be_empty()
            expect(card.locator('.detail').get_by_text(job['description']['coverage_note'], exact=False)).to_be_visible()
            for s in (job['description']['enrichment'] or {}).get('sections', []):
                assert s['text'] in card.locator('.detail').inner_text()
            for obs in job['observations']:
                history = card.locator('.record').filter(has=page.locator('pre')).filter(has_text=obs['archive_file']).first
                assert history.count(), job['id']
            card.locator(':scope > summary').click()
        thales = next(j for j in data['jobs'] if j['id']=='linkedin:4487019307')
        assert 'official_closed' in page.locator(f"#{thales['details_anchor']} > summary").inner_text()
        page.evaluate('(anchor)=>{location.hash=anchor}', thales['details_anchor'])
        expect(page.locator(f"#{thales['details_anchor']}" )).to_have_attribute('open', '')
        assert 'Direct platform-to-requisition linkage not established' in page.locator(f"#{thales['details_anchor']} .detail").inner_text()
        expect(page.locator(f"#{thales['details_anchor']} .detail a").filter(has_text='Sumber resmi tambahan')).to_have_attribute('href', thales['description']['enrichment']['supplemental_official_url'])
        # Mobile controls and details must fit without horizontal scrolling.
        page.close()
        page = browser.new_page(viewport={'width': 390, 'height': 844})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: network.append(request.url) if request.url.startswith(('https://', 'http://')) else None)
        page.set_content((ROOT / 'all-jobs.html').read_text())
        page.fill('#search','RAG')
        page.locator('#results > .job > summary').first.click()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile overflow'
        page.screenshot(path='/tmp/job-listings-mobile.png', full_page=True)
        page.close()
        page = browser.new_page(viewport={'width': 1280, 'height': 950})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: network.append(request.url) if request.url.startswith(('https://', 'http://')) else None)
        page.set_content((ROOT / 'all-jobs.html').read_text())
        page.screenshot(path='/tmp/job-listings-desktop.png', full_page=False)
        assert not errors, errors
        assert not network, network
        browser.close()
    print('PASS: real Chromium rendered HTML (set_content; managed browser blocks file:// navigation), every filter option, date/search/combined filters, sort/reset/empty state, all job details, deep links, Thales conflict, mobile layout, zero external requests or JS errors')


def main():
    data = json.loads((ROOT / 'all-jobs.json').read_text())
    verify_data(data)
    verify_future_updates()
    verify_browser(data)


if __name__ == '__main__':
    main()
