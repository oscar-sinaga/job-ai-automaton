import { expect, test } from '@playwright/test';

test('blocked page URL can be completed by pasting its actual description', async ({ page, request }) => {
	const api = 'http://127.0.0.1:8001';
	const headers = { 'X-API-Key': 'simulation-only-key' };
	const health = await request.get(`${api}/health`);
	expect(await health.json()).toMatchObject({ env: 'simulation', db: 'ok' });
	const captured = await request.post(`${api}/api/v1/jobs/capture`, {
		headers,
		data: {
			url: `https://example.com/blocked/${Date.now()}`,
			page_title: 'Just a moment...',
			raw_text: 'Performing security verification. Performance and Security by Cloudflare.',
			capture_method: 'extension',
			captured_at: new Date().toISOString()
		}
	});
	expect(captured.status()).toBe(201);
	const job = await captured.json();
	expect(job.capture_completeness).toBe('NEEDS_ENRICHMENT');
	await page.goto(`/jobs/${job.job_id}`);
	await expect(page.getByRole('button', { name: 'Generate CV', exact: true })).toBeDisabled();
	const editor = page.getByPlaceholder('Paste the full job description here…');
	await editor.fill('Performing security verification. Performance and Security by Cloudflare.');
	await page.getByRole('button', { name: 'Save description', exact: true }).click();
	await expect(page.getByText('Paste the job description, not the browser verification message.').first()).toBeVisible();
	const description = 'Example Data Engineer vacancy. Build and maintain Python and SQL pipelines, document data quality checks and collaborate with analysts.';
	await editor.fill(description);
	await page.getByRole('button', { name: 'Save description', exact: true }).click();
	await expect(page.getByRole('heading', { name: /Job description not saved yet/ })).toHaveCount(0);
	await expect(page.locator('pre')).toHaveText(description);
	await expect(page.getByRole('button', { name: 'Generate CV', exact: true })).toBeEnabled();
	const detail = await request.get(`${api}/api/v1/jobs/${job.job_id}`, { headers });
	const saved = await detail.json();
	expect(saved.capture_completeness).toBe('CAPTURED_COMPLETE');
	expect(saved.snapshots).toHaveLength(2);
	expect(saved.snapshots[0].raw_text_length).toBe(0);
});
