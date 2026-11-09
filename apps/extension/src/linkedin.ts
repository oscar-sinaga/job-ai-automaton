import type { ExtractionResult } from './types';

const DETAIL_ROOTS = [
	'.jobs-search__job-details--container', '.jobs-search__job-details',
	'.jobs-details__main-content', '.jobs-details', '.job-view-layout',
	'.scaffold-layout__detail', '[data-job-details]'
].join(',');
const DESCRIPTIONS = [
	'#job-details', '[data-job-description]', '.jobs-description-content__text',
	'.jobs-box__html-content', '.show-more-less-html__markup',
	'.description__text', '.jobs-description__content'
];
const TITLES = [
	'.job-details-jobs-unified-top-card__job-title', '.jobs-unified-top-card__job-title',
	'.topcard__title', '.top-card-layout__title'
];
const COMPANIES = [
	'.job-details-jobs-unified-top-card__company-name', '.jobs-unified-top-card__company-name',
	'.topcard__org-name-link'
];
const NON_JOB_CONTENT = [
	'aside', 'nav', 'footer',
	'.jobs-search-results-list', '.scaffold-layout__list', '.job-card-container',
	'.jobs-similar-jobs', '.jobs-company', '.jobs-poster', '.jobs-premium-upsell',
	'.artdeco-toast-item'
].join(',');
const EXCLUDED = [
	NON_JOB_CONTENT, 'header', 'button', 'script', 'style', 'form', '.visually-hidden'
].join(',');

function isVisible(element: Element): boolean {
	for (let node: Element | null = element; node; node = node.parentElement) {
		if (node.hasAttribute('hidden') || node.hasAttribute('inert') || node.getAttribute('aria-hidden') === 'true') return false;
		const style = (node as HTMLElement).style;
		if (style?.display === 'none' || ['hidden', 'collapse'].includes(style?.visibility)) return false;
		const computed = node.ownerDocument.defaultView?.getComputedStyle?.(node);
		if (computed?.display === 'none' || ['hidden', 'collapse'].includes(computed?.visibility ?? '')) return false;
	}
	return true;
}

function clean(value: string): string {
	return value.replace(/[ \t]+/g, ' ').replace(/ *\n */g, '\n').replace(/\n{3,}/g, '\n\n').trim();
}

function visibleText(element: Element): string {
	function read(node: Node): string {
		if (node.nodeType === 3) return node.textContent ?? '';
		if (node.nodeType !== 1) return '';
		const current = node as Element;
		if (!isVisible(current) || current.matches(EXCLUDED)) return '';
		if (current.tagName === 'BR') return '\n';
		const text = Array.from(current.childNodes).map(read).join('');
		return /^(DIV|P|LI|H[1-6]|SECTION|ARTICLE|UL|OL|TR)$/.test(current.tagName) ? `\n${text}\n` : text;
	}
	return clean(read(element));
}

function numericId(value: string | null): string | undefined {
	return value && /^\d+$/.test(value) ? value : undefined;
}

function directJobId(url: URL): string | undefined {
	return url.pathname.match(/^\/jobs\/view\/(?:[^/]+-)?([0-9]+)\/?$/)?.[1];
}

function linkedUrl(element: Element): URL | undefined {
	try {
		const url = new URL(element.getAttribute('href') ?? '', 'https://www.linkedin.com');
		return url.hostname === 'linkedin.com' || url.hostname.endsWith('.linkedin.com') ? url : undefined;
	} catch { return undefined; }
}

function requestedJobId(url: URL): string | undefined {
	const direct = directJobId(url);
	if (direct) return direct;
	if (!/^\/jobs(?:\/(?:search|search-results|collections(?:\/[^/]+)?))?\/?$/.test(url.pathname)) return undefined;
	const ids = url.searchParams.getAll('currentJobId');
	return ids.length === 1 ? numericId(ids[0]) : undefined;
}

function scopeFor(description: Element): Element {
	return description.closest(DETAIL_ROOTS) ?? description.closest('article') ?? description;
}

function metadataCandidates(scope: Element, description: Element, selector: string): Element[] {
	return Array.from(scope.querySelectorAll(selector)).filter(element =>
		!description.contains(element) && !element.closest(NON_JOB_CONTENT) && isVisible(element));
}

function metadataElement(scope: Element, description: Element, selectors: string[]): Element | undefined {
	// querySelectorAll with comma-separated selectors uses DOM order, not selector priority.
	for (const selector of selectors) {
		const candidate = metadataCandidates(scope, description, selector).find(element => visibleText(element));
		if (candidate) return candidate;
	}
	return undefined;
}

function detailMatchesJob(description: Element, scope: Element, expected: string, requireIdentity: boolean, explicitTitle?: Element): boolean {
	const ids = new Set<string>();
	function addIdentity(node: Element): void {
		for (const attribute of ['data-job-id', 'data-occludable-job-id']) {
			const id = numericId(node.getAttribute(attribute));
			if (id) ids.add(id);
		}
		const urn = node.getAttribute('data-entity-urn')?.match(/^urn:li:(?:fsd_)?jobPosting:(\d+)$/);
		if (urn) ids.add(urn[1]);
	}
	for (let node: Element | null = description; node; node = node.parentElement) addIdentity(node);
	for (const node of description.querySelectorAll('[data-job-id], [data-occludable-job-id], [data-entity-urn]')) {
		if (isVisible(node) && !node.closest(NON_JOB_CONTENT)) addIdentity(node);
	}
	const semanticTitles = metadataCandidates(scope, description, TITLES.join(','));
	const titles = explicitTitle ? [explicitTitle]
		: semanticTitles.length ? semanticTitles : metadataCandidates(scope, description, 'h1');
	for (const title of titles) {
		const links = title.matches('a[href]') ? [title] : Array.from(title.querySelectorAll('a[href]'));
		for (const link of links) {
			if (!isVisible(link)) continue;
			try {
				const linkedUrl = new URL(link.getAttribute('href') ?? '', 'https://www.linkedin.com');
				if (linkedUrl.hostname !== 'linkedin.com' && !linkedUrl.hostname.endsWith('.linkedin.com')) continue;
				const linkedId = directJobId(linkedUrl);
				if (linkedId) ids.add(linkedId);
			} catch { /* A malformed link does not establish the selected job's identity. */ }
		}
	}
	return (!requireIdentity || ids.size > 0) && Array.from(ids).every(id => id === expected);
}

interface DetailCandidate {
	description: Element;
	scope: Element;
	title?: Element;
	company?: Element;
	sdui?: true;
}

/** SDUI uses generated classes, a linked title and a dedicated expandable box.
 * Bound the box to its heading and the nearest detail column, never workspace. */
function sduiCandidates(document: Document, expected: string): DetailCandidate[] {
	const candidates: DetailCandidate[] = [];
	const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]'))
		.filter(element => isVisible(element) && !element.closest(NON_JOB_CONTENT)
			&& /^(about the job|tentang pekerjaan ini)$/i.test(visibleText(element)));
	for (const heading of headings) {
		const scope = heading.closest('[data-testid="lazy-column"], [data-component-type="LazyColumn"]');
		if (!scope || scope.matches('main, body, #root, #workspace')) continue;
		let headingWrapper = heading;
		while (headingWrapper.parentElement && headingWrapper.parentElement !== scope
			&& visibleText(headingWrapper.parentElement) === visibleText(heading)) {
			headingWrapper = headingWrapper.parentElement;
		}
		let following = headingWrapper.nextElementSibling;
		while (following && (!isVisible(following) || !visibleText(following))) following = following.nextElementSibling;
		if (!following || !scope.contains(following)
			|| following.matches('hr,h1,h2,h3,h4,h5,h6,[role="heading"]')) continue;
		const boxes = (following.matches('[data-testid="expandable-text-box"]') ? [following]
			: Array.from(following.querySelectorAll('[data-testid="expandable-text-box"]')))
			.filter(element => isVisible(element) && !element.closest(NON_JOB_CONTENT));
		if (boxes.length !== 1) continue;
		const description = boxes[0];
		if (Array.from(following.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]'))
			.some(element => isVisible(element) && !description.contains(element))) continue;
		// Only links before this heading may establish the selected header's identity.
		const ordered = Array.from(scope.querySelectorAll('a[href],h1,h2,h3,h4,h5,h6,[role="heading"]'));
		const preceding = new Set(ordered.slice(0, ordered.indexOf(heading)));
		const links = metadataCandidates(scope, description, 'a[href]')
			.filter(element => preceding.has(element))
			.map(element => {
				const url = linkedUrl(element);
				return { element, id: url ? directJobId(url) : undefined };
			})
			.filter(link => link.id);
		if (!links.length || links.some(link => link.id !== expected)) continue;
		const titles = links.map(link => link.element).filter(element => visibleText(element));
		if (!titles.length || new Set(titles.map(element => visibleText(element))).size !== 1) continue;
		const title = titles[0];
		let header = title;
		while (header.parentElement && header.parentElement !== scope) header = header.parentElement;
		if (header.contains(heading) || header.contains(description)) continue;
		const companies = Array.from(header.querySelectorAll('a[href]')).filter(element => {
			const url = linkedUrl(element);
			return url && /^\/company\/[^/]+(?:\/.*)?$/.test(url.pathname) && isVisible(element) && visibleText(element);
		});
		const company = new Set(companies.map(element => visibleText(element))).size === 1 ? companies[0] : undefined;
		candidates.push({ description, scope, title, company, sdui: true });
	}
	return candidates;
}

function collapsed(description: Element, scope: Element): boolean {
	const container = description.closest('.jobs-description') ?? description.closest('.description__text')
		?? description.closest('.jobs-description__content') ?? scope;
	const buttons = Array.from(container.querySelectorAll('button'));
	if (buttons.some(button => {
		if (!isVisible(button) || button.getAttribute('aria-expanded') === 'true') return false;
		if (button.matches('.show-more-less-html__button--more')) return true;
		return button.getAttribute('aria-expanded') === 'false'
			&& (button.matches('.jobs-description__footer-button')
				|| /see more|show more|lihat selengkapnya|tampilkan lebih/i.test(button.textContent ?? ''));
	})) return true;
	return !!description.closest('.jobs-description__content--condensed')
		&& !buttons.some(button => button.getAttribute('aria-expanded') === 'true');
}

/** LinkedIn search pages contain several jobs. Never use whole-page fallbacks. */
export function extractLinkedInJob(document: Document, pageUrl: string): ExtractionResult | undefined {
	let url: URL;
	try { url = new URL(pageUrl); } catch { return undefined; }
	if (url.hostname !== 'linkedin.com' && !url.hostname.endsWith('.linkedin.com')) return undefined;
	const id = requestedJobId(url);
	const jobUrl = id ? `https://www.linkedin.com/jobs/view/${id}/` : undefined;
	const partial: ExtractionResult = { text: '', extractor: 'none', truncated: false, jobUrl };
	if (!id) return partial;

	const descriptions = Array.from(document.querySelectorAll(DESCRIPTIONS.join(',')))
		.filter(element => isVisible(element) && !element.closest(NON_JOB_CONTENT));
	const priority = (element: Element): number => DESCRIPTIONS.findIndex(selector => element.matches(selector));
	// Prefer the authoritative job-description root over nested generic partials.
	// Equal-priority nested wrappers keep the complete outer text; separate panes stay ambiguous.
	const bounded = descriptions.filter(element => !descriptions.some(other => {
		if (element === other || scopeFor(element) !== scopeFor(other)) return false;
		if (!element.contains(other) && !other.contains(element)) return false;
		return priority(other) < priority(element) || (priority(other) === priority(element) && other.contains(element));
	}));
	let candidates: DetailCandidate[] = bounded.map(description => ({ description, scope: scopeFor(description) }))
		.filter(({ description, scope }) => detailMatchesJob(description, scope, id, !directJobId(url)));
	if (!candidates.length) candidates = sduiCandidates(document, id)
		.filter(({ description, scope, title }) => detailMatchesJob(description, scope, id, true, title));
	if (candidates.length !== 1) return partial;
	const { description, scope, sdui } = candidates[0];
	if (collapsed(description, sdui ? description : scope)) return partial;
	const text = visibleText(description);
	// Do not turn a title/company header into a complete job description.
	if (text.length < 40) return partial;
	const title = sdui ? candidates[0].title : metadataElement(scope, description, scope === description ? TITLES : [...TITLES, 'h1']);
	const company = sdui ? candidates[0].company : metadataElement(scope, description, COMPANIES);
	return {
		text: text.slice(0, 200_000), extractor: 'linkedin_detail', truncated: text.length > 200_000,
		jobTitle: title ? clean(visibleText(title)).replace(/\s+/g, ' ').slice(0, 500) || undefined : undefined,
		companyName: company ? clean(visibleText(company)).replace(/\s+/g, ' ').slice(0, 500) || undefined : undefined,
		jobUrl
	};
}
