import type { ExtractionResult } from './types';

const DESCRIPTION = '[data-automation="jobAdDetails"], [data-automation="jobDescription"], [data-automation="jobAdDetailsRichText"]';
const TITLE = '[data-automation="job-detail-title"]';
const COMPANY = ['[data-automation="job-detail-company-link"]', '[data-automation="advertiser-name"]'];
const DETAIL = '[data-automation="jobDetails"], [data-automation="job-details"], [data-automation="jobDetail"]';
const NON_JOB = 'aside, nav, footer, script, style, form, [data-automation="similarJobs"], [data-automation="companyProfile"]';
const EXCLUDED = `${NON_JOB}, button`;

export function isJobstreetHost(host: string): boolean {
	return host === 'jobstreet.com' || host.endsWith('.jobstreet.com')
		|| host === 'jobstreet.co.id' || host.endsWith('.jobstreet.co.id');
}

function canonicalHost(host: string): string {
	return host === 'jobstreet.co.id' || host.endsWith('.jobstreet.co.id') ? 'id.jobstreet.com' : host.replace(/^www\./, '');
}

function jobId(url: URL): string | undefined {
	const direct = url.pathname.match(/^\/(?:id\/)?job\/([0-9]+)\/?$/);
	if (direct) return direct[1];
	const path = url.pathname.replace(/^\/id(?=\/|$)/, '').replace(/\/$/, '') || '/';
	if (!/^(?:\/|\/jobs|\/jobs-in-[^/]+|\/[^/]+-jobs(?:\/in-[^/]+)?)(?:\/(?:full-time|part-time|contract-temp|casual-vacation))?$/.test(path)) return undefined;
	const ids = url.searchParams.getAll('jobId');
	return ids.length === 1 && /^[0-9]+$/.test(ids[0]) ? ids[0] : undefined;
}

function visible(element: Element): boolean {
	for (let node: Element | null = element; node; node = node.parentElement) {
		if (node.hasAttribute('hidden') || node.hasAttribute('inert') || node.getAttribute('aria-hidden') === 'true') return false;
		const style = (node as HTMLElement).style;
		const computed = node.ownerDocument.defaultView?.getComputedStyle?.(node);
		if (style?.display === 'none' || computed?.display === 'none'
			|| ['hidden', 'collapse'].includes(style?.visibility)
			|| ['hidden', 'collapse'].includes(computed?.visibility ?? '')) return false;
	}
	return true;
}

function text(element: Element): string {
	function read(node: Node): string {
		if (node.nodeType === 3) return node.textContent ?? '';
		if (node.nodeType !== 1) return '';
		const el = node as Element;
		// Employer labels may themselves be buttons; controls nested in the JD
		// still do not become description text.
		if (!visible(el) || (el.matches(EXCLUDED) && !(el === element && el.tagName === 'BUTTON'))) return '';
		if (el.tagName === 'BR') return '\n';
		const content = Array.from(el.childNodes).map(read).join('');
		if (/^(TD|TH)$/.test(el.tagName)) return `\t${content}\t`;
		return /^(DIV|P|LI|H[1-6]|SECTION|ARTICLE|UL|OL|TR|TABLE|PRE)$/.test(el.tagName) ? `\n${content}\n` : content;
	}
	return read(element).replace(/[ \t]+/g, ' ').replace(/ *\n */g, '\n').replace(/\n{3,}/g, '\n\n').trim();
}

function first(scope: Element, selectors: string[], description?: Element): Element | undefined {
	for (const selector of selectors) {
		const result = Array.from(scope.querySelectorAll(selector)).find(node => !description?.contains(node)
			&& !node.closest(NON_JOB) && visible(node) && text(node));
		if (result) return result;
	}
	return undefined;
}

// Search headers and result cards use other markers. Never climb into the
// whole page just to obtain a title or company for an isolated description.
function scopeFor(description: Element): Element {
	const known = description.closest(DETAIL);
	if (known) return known;
	for (let node = description.parentElement; node && !node.matches('body, html, main, [role="main"]'); node = node.parentElement) {
		if (Array.from(node.querySelectorAll(DESCRIPTION)).filter(visible).some(other => !description.contains(other) && !other.contains(description))) break;
		if (first(node, [TITLE], description)) return node;
	}
	return description;
}

type Posting = { title?: string; hiringOrganization?: { name?: string }; url?: string; '@id'?: string };
function postings(document: Document): Posting[] {
	const result: Posting[] = [];
	function visit(value: unknown): void {
		if (Array.isArray(value)) { value.forEach(visit); return; }
		if (!value || typeof value !== 'object') return;
		const obj = value as Record<string, unknown>;
		if (obj['@type'] === 'JobPosting' || (Array.isArray(obj['@type']) && obj['@type'].includes('JobPosting'))) result.push(obj as Posting);
		if (obj['@graph']) visit(obj['@graph']);
	}
	for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
		try { visit(JSON.parse(script.textContent ?? '')); } catch { /* malformed structured data is not a capture source */ }
	}
	return result;
}

function identityMatches(description: Element, scope: Element, url: URL, expected: string, structured: Posting[]): boolean {
	const ids = new Set<string>();
	function addIdentity(node: Element): void {
		for (const attr of ['data-job-id', 'data-jobid']) {
			const id = node.getAttribute(attr);
			if (id && /^[0-9]+$/.test(id)) ids.add(id);
		}
	}
	for (let node: Element | null = description; node; node = node.parentElement) {
		addIdentity(node);
		if (node === scope) break;
	}
	for (const node of description.querySelectorAll('[data-job-id], [data-jobid]')) {
		if (visible(node) && !node.closest(EXCLUDED)) addIdentity(node);
	}
	for (const link of scope.querySelectorAll(`${TITLE} a[href], a${TITLE}[href]`)) {
		if (!visible(link) || description.contains(link) || link.closest(NON_JOB)) continue;
		try {
			const linked = new URL(link.getAttribute('href')!, url);
			if (isJobstreetHost(linked.hostname) && canonicalHost(linked.hostname) === canonicalHost(url.hostname)) {
				const id = jobId(linked);
				if (id) ids.add(id);
			}
		} catch { /* ignore malformed links */ }
	}
	if (Array.from(ids).some(id => id !== expected)) return false;
	const title = first(scope, [TITLE], description);
	const company = first(scope, COMPANY, description);
	const normalize = (value: string) => value.replace(/\s+/g, ' ').trim().toLowerCase();
	const matching = structured.filter(posting => {
		try {
			const source = posting.url ?? posting['@id'];
			if (typeof source !== 'string' || !source.trim()) return false;
			const linked = new URL(source.trim(), url);
			return ['http:', 'https:'].includes(linked.protocol) && isJobstreetHost(linked.hostname)
				&& canonicalHost(linked.hostname) === canonicalHost(url.hostname)
				&& linked.pathname.match(/^\/(?:id\/)?job\/([0-9]+)\/?$/)?.[1] === expected;
		} catch { return false; }
	});
	const verified = matching.some(posting => title && typeof posting.title === 'string'
		&& normalize(posting.title) === normalize(text(title))
		&& (!company || (typeof posting.hiringOrganization?.name === 'string'
			&& normalize(posting.hiringOrganization.name) === normalize(text(company)))));
	// A changing search URL alone cannot prove that an old detail pane has loaded.
	return /^\/(?:id\/)?job\/[0-9]+\/?$/.test(url.pathname) || ids.has(expected) || verified;
}

function collapsed(description: Element): boolean {
	const buttons: Element[] = Array.from(description.querySelectorAll('button'));
	const next = description.nextElementSibling;
	if (next && visible(next)) {
		const following = next.matches('button') ? [next] : Array.from(next.querySelectorAll('button'));
		buttons.push(...following.filter(button => /^(?:see more|show more|lihat selengkapnya|tampilkan lebih|baca selengkapnya)[.!\s]*$/i.test(button.textContent?.trim() ?? '')));
	}
	return buttons.some(button => visible(button) && button.getAttribute('aria-expanded') === 'false');
}

/** Jobstreet's results, insights and company sections are never JD fallbacks. */
export function extractJobstreetJob(document: Document, pageUrl: string): ExtractionResult | undefined {
	let url: URL;
	try { url = new URL(pageUrl); } catch { return undefined; }
	if (!isJobstreetHost(url.hostname)) return undefined;
	const id = jobId(url);
	const host = canonicalHost(url.hostname);
	const jobUrl = id ? `https://${host}/job/${id}` : undefined;
	const partial: ExtractionResult = { text: '', extractor: 'none', truncated: false, jobUrl };
	if (!id) return partial;
	const nodes = Array.from(document.querySelectorAll(DESCRIPTION)).filter(visible)
		.filter(node => !node.closest('[data-automation="job-card"], [data-automation="jobCard"], aside'));
	// Keep the outer bounded JD: rich-text children may cover only one paragraph.
	const descriptions = nodes.filter(node => !nodes.some(other => node !== other && other.contains(node)));
	const structured = postings(document);
	const candidates = descriptions.map(description => ({ description, scope: scopeFor(description) }))
		.filter(({ description, scope }) => identityMatches(description, scope, url, id, structured));
	if (candidates.length !== 1) return partial;
	const { description, scope } = candidates[0];
	if (collapsed(description)) return partial;
	const raw = text(description);
	if (raw.length < 40) return partial;
	const title = first(scope, [TITLE], description);
	const company = first(scope, COMPANY, description);
	return {
		text: raw.slice(0, 200_000), truncated: raw.length > 200_000, extractor: 'jobstreet_detail', jobUrl,
		jobTitle: title ? text(title).replace(/\s+/g, ' ').slice(0, 500) || undefined : undefined,
		companyName: company ? text(company).replace(/\s+/g, ' ').slice(0, 500) || undefined : undefined
	};
}
