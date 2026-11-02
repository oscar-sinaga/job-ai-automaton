import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

const API = 'http://127.0.0.1:8001';
const headers = { 'X-API-Key': 'simulation-only-key' };
const statement = 'Built Python pipelines for café operations and warehouse reporting.';
const secondStatement = 'Automated SQL data-quality checks for daily inventory reports.';

test('example profile → job → CV versions → approval → PDF → application → analytics', async ({
	page,
	request
}, testInfo) => {
	// Refuse mutations unless the explicit offline server is healthy.
	const health = await request.get(`${API}/health`);
	expect(await health.json()).toMatchObject({ env: 'simulation', db: 'ok' });
	const before = await (await request.get(`${API}/api/v1/dashboard`, { headers })).json();
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	page.on('console', (message) => {
		if (message.type() === 'error') errors.push(message.text());
	});
	async function saveCareerForm(button: string) {
		const refresh = page.waitForResponse((response) => response.url().includes('/career-profile/__data.json') && response.ok(), { timeout: 10_000 });
		await page.getByRole('button', { name: button, exact: true }).click();
		await refresh;
	}
	await page.route('**/*', async (route) => {
		const url = new URL(route.request().url());
		if (url.hostname !== '127.0.0.1') {
			errors.push(`Unexpected external browser request: ${url.origin}`);
			return route.abort();
		}
		return route.continue();
	});

	await page.goto('/career-profile', { waitUntil: 'networkidle' });
	await page.getByLabel('CV name', { exact: true }).fill('Simulation Candidate – José');
	await page.getByLabel('CV email', { exact: true }).fill('simulation@example.com');
	await saveCareerForm('Save preferences');
	await expect(page.getByLabel('CV name', { exact: true })).toHaveValue('Simulation Candidate – José');
	// Saving unchanged values must not reset the visible, persisted contacts.
	await saveCareerForm('Save preferences');
	await expect(page.getByLabel('CV name', { exact: true })).toHaveValue('Simulation Candidate – José');
	await expect(page.getByLabel('CV email', { exact: true })).toHaveValue('simulation@example.com');
	await page.locator('textarea[name="summary"]').fill('Example profile for offline simulation.');
	await saveCareerForm('Save');
	await saveCareerForm('Save');
	await expect(page.locator('textarea[name="summary"]')).toHaveValue('Example profile for offline simulation.');
	await page.getByPlaceholder('Company', { exact: true }).fill(`Example Warehouse ${testInfo.project.name}`);
	await page.getByPlaceholder('Title', { exact: true }).fill('Data Engineer');
	await page.getByLabel('Start date', { exact: true }).fill('2022-01-01');
	await page.getByLabel('Current role').check();
	await saveCareerForm('Add experience');
	await expect(page.getByPlaceholder('Company', { exact: true })).toHaveValue('');
	await expect(page.getByText(`Example Warehouse ${testInfo.project.name}`, { exact: false }).first()).toBeVisible();
	for (const text of [statement, secondStatement]) {
		const count = await page.getByText(text, { exact: true }).count();
		await page.getByPlaceholder('What did you do? (in your own words)').fill(text);
		await page.locator('select[name="experience_id"]').selectOption({
			label: `Data Engineer @ Example Warehouse ${testInfo.project.name}`
		});
		await page.getByPlaceholder('skill tags (comma-separated)', { exact: true }).fill('Python, SQL');
		await saveCareerForm('Add achievement');
		await expect(page.getByText(text, { exact: true })).toHaveCount(count + 1);
		await expect(page.getByPlaceholder('What did you do? (in your own words)')).toHaveValue('');
	}
	await page.waitForLoadState('networkidle');
	await page.screenshot({ path: testInfo.outputPath('career-profile.png'), fullPage: true });
	expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
	await page.goto('/jobs', { waitUntil: 'networkidle' });
	await page.getByLabel('Job URL', { exact: true }).fill(`https://example.com/simulation/${testInfo.project.name}/${Date.now()}`);
	await page.getByRole('button', { name: 'Paste full job description (recommended)' }).click();
	await page.getByLabel('Job description text').fill(
		'SIMULATION: Data Engineer at Example Warehouse. Build Python and SQL pipelines for inventory reporting, reconcile warehouse transactions and document data quality checks. This is a fictional vacancy for an offline browser test. '.repeat(3)
	);
	await page.getByRole('button', { name: 'Save job', exact: true }).click();
	await expect(page.getByText('Saved.', { exact: true })).toBeVisible();
	await page.locator('tbody tr').first().getByRole('link').click();
	await expect(page).toHaveURL(/\/jobs\/\d+$/);
	const jobId = Number(page.url().split('/').pop());
	await page.getByRole('button', { name: 'Generate CV', exact: true }).click();
	await expect(page).toHaveURL(/\/cv\/\d+$/);
	const originalId = Number(page.url().split('/').pop());
	await expect(page.getByText(statement, { exact: true }).first()).toBeVisible();
	await expect(page.getByRole('button', { name: 'Export PDF' })).toBeDisabled();
	const blocked = await request.post(`${API}/api/v1/cv/${originalId}/export`, { headers });
	expect(blocked.status()).toBe(409);
	// Editing creates a new, unapproved version and preserves the original.
	await page.locator('form:has(input[value="summary"])').getByRole('button', { name: 'remove', exact: true }).click();
	await expect(page).not.toHaveURL(new RegExp(`/cv/${originalId}$`));
	const editedId = Number(page.url().split('/').pop());
	await expect(page.getByText('(removed)', { exact: true })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Export PDF' })).toBeDisabled();
	const original = await (await request.get(`${API}/api/v1/cv/${originalId}`, { headers })).json();
	expect(original.sections.summary.text).not.toBe('');
	await page.getByRole('checkbox', { name: /I reviewed the CV/ }).check();
	await page.getByRole('button', { name: 'Approve CV', exact: true }).click();
	await expect(page.getByText('This version has been reviewed and approved.')).toBeVisible();
	await page.getByRole('button', { name: 'Export PDF', exact: true }).click();
	const downloadPromise = page.waitForEvent('download');
	await page.getByRole('link', { name: 'Download PDF', exact: true }).click();
	const download = await downloadPromise;
	const pdfPath = testInfo.outputPath('simulation-cv.pdf');
	await download.saveAs(pdfPath);
	expect((await readFile(pdfPath)).subarray(0, 4).toString()).toBe('%PDF');
	await testInfo.attach('downloaded-pdf', { path: pdfPath, contentType: 'application/pdf' });
	const exportAgain = await request.post(`${API}/api/v1/cv/${editedId}/export`, { headers });
	expect(exportAgain.ok()).toBeTruthy();
	const artifact = await exportAgain.json();
	const exportedAgain = await request.get(`${API}${artifact.download_url}`, { headers });
	expect(Buffer.compare(await exportedAgain.body(), await readFile(pdfPath))).toBe(0);
	await page.screenshot({ path: testInfo.outputPath('cv-review.png'), fullPage: true });
	await page.getByRole('link', { name: '← Job Detail', exact: true }).click();
	await page.getByLabel('Submitted CV').selectOption(String(editedId));
	await page.getByRole('button', { name: 'Mark as Applied', exact: true }).click();
	await expect(page.getByText('APPLIED', { exact: true }).first()).toBeVisible();
	const application = await (await request.get(`${API}/api/v1/jobs/${jobId}/application`, { headers })).json();
	expect(application.submitted_cv_version_id).toBe(editedId);
	await page.getByRole('button', { name: 'Interview received', exact: true }).click();
	await expect(page.getByText('INTERVIEW', { exact: true }).first()).toBeVisible();
	// Re-approving must not move an existing application backwards.
	await request.post(`${API}/api/v1/cv/${editedId}/approve`, { headers });
	const job = await (await request.get(`${API}/api/v1/jobs/${jobId}`, { headers })).json();
	expect(job.current_status).toBe('INTERVIEW');
	await page.goto('/analytics', { waitUntil: 'networkidle' });
	await expect(page.getByRole('heading', { name: 'Analytics', exact: true })).toBeVisible();
	const after = await (await request.get(`${API}/api/v1/dashboard`, { headers })).json();
	expect(after.kpis.saved).toBe(before.kpis.saved + 1);
	expect(after.kpis.applied).toBe(before.kpis.applied + 1);
	expect(after.kpis.interview).toBe(before.kpis.interview + 1);
	await page.screenshot({ path: testInfo.outputPath('analytics.png'), fullPage: true });
	expect(errors).toEqual([]);
});
