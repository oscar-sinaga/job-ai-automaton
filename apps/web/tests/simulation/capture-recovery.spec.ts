import { expect, test } from '@playwright/test';

test('hiding and reopening a job description preserves the draft', async ({ page, request }) => {
	const headers = { 'X-API-Key': 'simulation-only-key' };
	const health = await request.get('http://127.0.0.1:8001/health');
	expect(await health.json()).toMatchObject({ env: 'simulation', db: 'ok' });
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	page.on('console', (message) => {
		if (message.type() === 'error') errors.push(message.text());
	});
	await page.route('**/*', (route) => {
		const url = new URL(route.request().url());
		if (url.hostname !== '127.0.0.1') {
			errors.push(`Unexpected external browser request: ${url.origin}`);
			return route.abort();
		}
		return route.continue();
	});
	await page.goto('/jobs');
	await page.getByLabel('Job URL', { exact: true }).fill('https://example.com/offline-draft');
	await page.getByRole('button', { name: 'Paste full job description (recommended)' }).click();
	const description = 'Fictional job description kept while hiding and reopening the editor.';
	await page.getByLabel('Job description text').fill(description);
	await page.getByRole('button', { name: 'Hide', exact: true }).click();
	await expect(page.getByLabel('Job description text')).not.toBeVisible();
	await page.getByRole('button', { name: 'Paste full job description (recommended)' }).click();
	await expect(page.getByLabel('Job description text')).toHaveValue(description);
	await expect(page.getByLabel('Job URL', { exact: true })).toHaveValue('https://example.com/offline-draft');
	// Hiding means collapse, not discard: capture must retain the full description.
	await page.getByRole('button', { name: 'Hide', exact: true }).click();
	await page.getByRole('button', { name: 'Save job', exact: true }).click();
	await expect(page.getByText('Saved.', { exact: true })).toBeVisible();
	await expect(page.getByLabel('Job URL', { exact: true })).toHaveValue('');
	await page.getByRole('button', { name: 'Paste full job description (recommended)' }).click();
	await expect(page.getByLabel('Job description text')).toHaveValue('');
	await page.locator('tbody tr').first().getByRole('link').click();
	await expect(page).toHaveURL(/\/jobs\/\d+$/);
	const jobId = page.url().split('/').pop();
	const raw = await request.get(`http://127.0.0.1:8001/api/v1/jobs/${jobId}/raw`, { headers });
	expect(raw.ok()).toBeTruthy();
	expect((await raw.json()).raw_text).toBe(description);
	expect(errors).toEqual([]);
});
