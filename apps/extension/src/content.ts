// Generic-first extraction (docs/08_BROWSER_EXTENSION_DESIGN.md §4). Runs only
// when injected via chrome.scripting.executeScript after the user clicks Save
// (activeTab permission) -- never on page load, never in the background.
//
// Sends its result back via chrome.runtime.sendMessage rather than relying on
// executeScript's "last statement completion value" mechanism: a bundled
// script's top-level code ends up inside an IIFE, and a function without an
// explicit `return` always completes as `undefined`, not as the value of its
// last expression -- that mechanism only applies to unwrapped, directly
// eval'd code. Messaging is robust regardless of how the bundler wraps this.

import type { ExtractionResult, ExtractorUsed } from './types';

const MIN_COMPLETE_LENGTH = 400; // mirrors the server's own floor (docs/05 §3)
const MAX_CHARS = 200_000; // docs/05 §3: capped, never rejected

function cleanText(text: string): string {
	return text
		.replace(/[ \t]+/g, ' ')
		.replace(/\n{3,}/g, '\n\n')
		.trim();
}

function cap(text: string): { text: string; truncated: boolean } {
	if (text.length > MAX_CHARS) return { text: text.slice(0, MAX_CHARS), truncated: true };
	return { text, truncated: false };
}

/** The densest text block: highest text-length-to-link-density ratio among
 * candidate containers, favouring large blocks that aren't mostly nav links. */
function densestTextBlock(): string {
	const candidates = document.querySelectorAll('div, section, article, main');
	let best = '';
	let bestScore = 0;

	for (const el of candidates) {
		const text = (el as HTMLElement).innerText ?? '';
		if (text.length < MIN_COMPLETE_LENGTH) continue;

		const linkTextLength = Array.from(el.querySelectorAll('a')).reduce(
			(sum, a) => sum + ((a as HTMLElement).innerText?.length ?? 0),
			0
		);
		const linkDensity = linkTextLength / (text.length + 1);
		const score = text.length * (1 - linkDensity);

		if (score > bestScore) {
			bestScore = score;
			best = text;
		}
	}
	return best;
}

export function extractGenericJobText(): ExtractionResult {
	const selection = cleanText(window.getSelection()?.toString() ?? '');
	if (selection.length >= MIN_COMPLETE_LENGTH) {
		return { ...cap(selection), extractor: 'selection' as ExtractorUsed };
	}

	const mainEl = document.querySelector('main, [role="main"], article') as HTMLElement | null;
	const mainText = cleanText(mainEl?.innerText ?? '');
	if (mainText.length >= MIN_COMPLETE_LENGTH) {
		return { ...cap(mainText), extractor: 'main' as ExtractorUsed };
	}

	const densest = cleanText(densestTextBlock());
	if (densest.length >= MIN_COMPLETE_LENGTH) {
		return { ...cap(densest), extractor: 'densest_block' as ExtractorUsed };
	}

	const bodyText = cleanText(document.body?.innerText ?? '');
	const { text, truncated } = cap(bodyText);
	return { text, truncated, extractor: (text ? 'body_fallback' : 'none') as ExtractorUsed };
}

(function run() {
	const result = extractGenericJobText();
	chrome.runtime.sendMessage({ type: 'EXTRACTION_RESULT', payload: result });
})();
