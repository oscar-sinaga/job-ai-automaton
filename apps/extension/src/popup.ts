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
		statusEl.textContent = `Saved as ${response.ref} (${response.captureCompleteness})${dup}`;
	});
});
