export interface JobMetadata {
	jobTitle?: string;
	companyName?: string;
}

function text(value: unknown): string | undefined {
	if (typeof value !== 'string') return undefined;
	return value.replace(/\s+/g, ' ').trim().slice(0, 500) || undefined;
}

function property(root: ParentNode, name: string): string | undefined {
	const element = root.querySelector(`[itemprop="${name}"]`);
	return text(element?.getAttribute('content') || element?.textContent);
}

function jobPosting(value: unknown): Record<string, unknown> | undefined {
	if (Array.isArray(value)) {
		return value.map(jobPosting).find(Boolean);
	}
	if (!value || typeof value !== 'object') return undefined;
	const node = value as Record<string, unknown>;
	const types = Array.isArray(node['@type']) ? node['@type'] : [node['@type']];
	if (types.includes('JobPosting')) return node;
	return jobPosting(node['@graph']);
}

export function extractJobMetadata(): JobMetadata {
	let structured: Record<string, unknown> | undefined;
	for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
		try {
			structured = jobPosting(JSON.parse(script.textContent || 'null'));
			if (structured) break;
		} catch {
			// Invalid third-party JSON must not prevent saving the page.
		}
	}

	const root = document.querySelector('[itemtype$="/JobPosting"]') || document;
	const organization = structured?.hiringOrganization;
	const company = organization && typeof organization === 'object'
		? (organization as Record<string, unknown>).name
		: organization;
	const companyElement = root.querySelector('[itemprop="hiringOrganization"]');
	const companyName = text(company)
		|| text(companyElement?.getAttribute('content'))
		|| (companyElement && property(companyElement, 'name'))
		|| text(companyElement?.textContent);

	return {
		jobTitle: text(structured?.title) || property(root, 'title')
			|| text(root.querySelector('h1')?.textContent),
		companyName: companyName || undefined
	};
}
