const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

const baseUrlInput = document.getElementById('apiBaseUrl') as HTMLInputElement;
const apiKeyInput = document.getElementById('apiKey') as HTMLInputElement;
const statusEl = document.getElementById('status') as HTMLParagraphElement;
const saveButton = document.getElementById('save') as HTMLButtonElement;

chrome.storage.local.get(['apiBaseUrl', 'apiKey']).then((stored) => {
	baseUrlInput.value = (stored.apiBaseUrl as string) || DEFAULT_API_BASE_URL;
	apiKeyInput.value = (stored.apiKey as string) || '';
});

saveButton.addEventListener('click', () => {
	chrome.storage.local
		.set({
			apiBaseUrl: baseUrlInput.value.trim() || DEFAULT_API_BASE_URL,
			apiKey: apiKeyInput.value.trim()
		})
		.then(() => {
			statusEl.textContent = 'Saved.';
			setTimeout(() => (statusEl.textContent = ''), 2000);
		});
});
