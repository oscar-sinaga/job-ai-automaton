// MV3 service worker. Holds the API key (read from chrome.storage.local, set
// via the options page) and is the only place that calls the API -- the popup
// and content script never see it (docs/08 §6).

import type { CaptureOutcome, ExtractionResult } from './types';

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000/api/v1';
const EXTRACTION_TIMEOUT_MS = 5000;

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
	if (message?.type === 'CAPTURE_ACTIVE_TAB') {
		captureActiveTab()
			.then(sendResponse)
			.catch((error: unknown) =>
				sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) })
			);
		return true; // keep the message channel open for the async sendResponse
	}
	return undefined;
});

async function getConfig(): Promise<{ apiBaseUrl: string; apiKey: string }> {
	const stored = await chrome.storage.local.get(['apiBaseUrl', 'apiKey']);
	return {
		apiBaseUrl: (stored.apiBaseUrl as string) || DEFAULT_API_BASE_URL,
		apiKey: (stored.apiKey as string) || ''
	};
}

function extractFromTab(tabId: number): Promise<ExtractionResult> {
	return new Promise((resolve, reject) => {
		const timeout = setTimeout(() => {
			chrome.runtime.onMessage.removeListener(listener);
			reject(new Error('Extraction timed out'));
		}, EXTRACTION_TIMEOUT_MS);

		function listener(message: unknown, sender: chrome.runtime.MessageSender) {
			const m = message as { type?: string; payload?: ExtractionResult };
			if (m?.type === 'EXTRACTION_RESULT' && sender.tab?.id === tabId) {
				clearTimeout(timeout);
				chrome.runtime.onMessage.removeListener(listener);
				resolve(m.payload as ExtractionResult);
			}
		}
		chrome.runtime.onMessage.addListener(listener);

		chrome.scripting.executeScript({ target: { tabId }, files: ['content.js'] }).catch((e) => {
			clearTimeout(timeout);
			chrome.runtime.onMessage.removeListener(listener);
			reject(e);
		});
	});
}

async function captureActiveTab(): Promise<CaptureOutcome> {
	const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
	if (!tab?.id || !tab.url) {
		throw new Error('No active tab to save');
	}

	// A page the browser won't let content scripts run on (chrome://, the Web
	// Store, PDFs) must still fail gracefully with a clear message, not a
	// silent no-op.
	let extraction: ExtractionResult;
	try {
		extraction = await extractFromTab(tab.id);
	} catch {
		extraction = { text: '', extractor: 'none', truncated: false };
	}

	const { apiBaseUrl, apiKey } = await getConfig();
	if (!apiKey) {
		throw new Error('Set the API key in the extension options first');
	}

	const response = await fetch(`${apiBaseUrl}/jobs/capture`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			'X-API-Key': apiKey,
			'Idempotency-Key': crypto.randomUUID()
		},
		body: JSON.stringify({
			url: tab.url,
			source_hint: safeHostname(tab.url),
			page_title: tab.title ?? '',
			job_title: extraction.jobTitle,
			company_name: extraction.companyName,
			raw_text: extraction.text || undefined,
			capture_method: 'extension',
			captured_at: new Date().toISOString(),
			metadata: {
				page_access: extraction.pageAccess,
				extractor: extraction.extractor,
				truncated: extraction.truncated,
				extension_version: chrome.runtime.getManifest().version
			}
		}),
		signal: AbortSignal.timeout(10_000)
	}).catch(() => {
		throw new Error('Cannot reach OSCAR API. Check that the backend is running and the API URL is correct, then try Save again.');
	});

	const body = await response.json().catch(() => ({}));
	if (!response.ok) {
		throw new Error(body.message ?? `Save failed (${response.status})`);
	}

	return {
		ok: true,
		ref: body.ref,
		captureCompleteness: body.capture_completeness,
		isDuplicate: body.duplicate_of_job_id !== null && body.duplicate_of_job_id !== undefined
	};
}

function safeHostname(url: string): string | undefined {
	try {
		return new URL(url).hostname;
	} catch {
		return undefined;
	}
}
