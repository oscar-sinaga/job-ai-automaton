import type { CaptureOutcome } from './types';

const saveButton = document.getElementById('save') as HTMLButtonElement;
const statusEl = document.getElementById('status') as HTMLParagraphElement;

saveButton.addEventListener('click', () => {
	saveButton.disabled = true;
	statusEl.textContent = 'Saving…';

	chrome.runtime.sendMessage({ type: 'CAPTURE_ACTIVE_TAB' }, (response: CaptureOutcome) => {
		saveButton.disabled = false;

		if (chrome.runtime.lastError) {
			statusEl.textContent = `Error: ${chrome.runtime.lastError.message}`;
			return;
		}
		if (!response?.ok) {
			statusEl.textContent = `Error: ${response?.error ?? 'unknown error'}`;
			return;
		}

		const dup = response.isDuplicate ? ' — possible duplicate' : '';
		if (response.captureCompleteness === 'NEEDS_ENRICHMENT') {
			statusEl.textContent = `URL saved as ${response.ref}${dup}. Full description was not captured. Open the job detail, expand its description, wait for it to load, then Save again. You can also paste the description in OSCAR Job Inbox.`;
			return;
		}
		if (response.captureCompleteness === 'CAPTURED_PARTIAL') {
			statusEl.textContent = `Partially saved as ${response.ref}${dup}. Full description was not captured. Open the job detail, expand its description, wait for it to load, then Save again; or paste it in OSCAR Job Inbox.`;
			return;
		}
		statusEl.textContent = `Saved as ${response.ref} (${response.captureCompleteness})${dup}`;
	});
});
