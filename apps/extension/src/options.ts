import { DEFAULT_API_BASE_URL, normalizeApiBaseUrl } from './api-config';

const baseUrlInput = document.getElementById('apiBaseUrl') as HTMLInputElement;
const apiKeyInput = document.getElementById('apiKey') as HTMLInputElement;
const statusEl = document.getElementById('status') as HTMLParagraphElement;
const saveButton = document.getElementById('save') as HTMLButtonElement;

chrome.storage.local.get(['apiBaseUrl', 'apiKey']).then((stored) => {
	baseUrlInput.value = (stored.apiBaseUrl as string) || DEFAULT_API_BASE_URL;
	apiKeyInput.value = (stored.apiKey as string) || '';
});

saveButton.addEventListener('click', async () => {
	try {
		const apiBaseUrl = normalizeApiBaseUrl(baseUrlInput.value);
		await chrome.storage.local.set({
			apiBaseUrl,
			apiKey: apiKeyInput.value.trim()
		});
		baseUrlInput.value = apiBaseUrl;
		statusEl.style.color = '#059669';
		statusEl.textContent = 'Saved.';
	} catch (error) {
		statusEl.style.color = '#b91c1c';
		statusEl.textContent = error instanceof Error ? error.message : 'Could not save settings.';
	}
});
