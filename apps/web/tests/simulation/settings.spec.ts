import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("settings persist, export real data, and require explicit scoped deletion", async ({
  page,
  request,
}, testInfo) => {
  const api = process.env.SIMULATION_API_ORIGIN ?? "http://127.0.0.1:8001";
  const headers = {
    "X-API-Key": process.env.SIMULATION_API_KEY ?? "simulation-only-key",
  };
  const captured = await request.post(`${api}/api/v1/jobs/capture`, {
    headers,
    data: {
      url: `https://example.com/settings/${testInfo.project.name}/${Date.now()}`,
      page_title: "Synthetic settings vacancy",
      raw_text: "Fictional data engineering vacancy. ".repeat(20),
      capture_method: "extension",
      captured_at: new Date().toISOString(),
    },
  });
  expect(captured.status()).toBe(201);
  const job = await captured.json();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/settings");
  await expect(
    page.getByRole("heading", { name: "Settings", exact: true }),
  ).toBeVisible();
  await page.getByLabel("CV heading language").selectOption("id");
  await page.getByLabel("PDF layout").selectOption("compact");
  await page.getByLabel("Maximum bullets per role").fill("2");
  await page
    .getByRole("button", { name: "Save CV defaults", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Settings saved." }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("CV heading language")).toHaveValue("id");
  await expect(page.getByLabel("PDF layout")).toHaveValue("compact");
  await expect(page.getByLabel("Maximum bullets per role")).toHaveValue("2");
  await page.getByLabel("OpenAI model ID").fill("gpt-6-luna");
  await page.getByLabel("Maximum output tokens").fill("2048");
  await page
    .getByRole("button", { name: "Save AI preferences", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Settings saved." }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Maximum output tokens")).toHaveValue("2048");
  await expect(page.getByLabel("API base URL")).toHaveValue(
    "http://127.0.0.1:5173/api/v1",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: testInfo.outputPath("settings.png"),
    fullPage: true,
  });

  const jsonPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "JSON only" }).click();
  const jsonDownload = await jsonPromise;
  const jsonPath = testInfo.outputPath("workspace.json");
  await jsonDownload.saveAs(jsonPath);
  const exported = await readFile(jsonPath, "utf8");
  expect(exported).toContain("Synthetic settings vacancy");
  expect(exported).not.toContain("simulation-only-key");
  expect(exported).not.toContain("deletion_token_hash");
  const zipPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download ZIP" }).click();
  const zipDownload = await zipPromise;
  const zipPath = testInfo.outputPath("workspace.zip");
  await zipDownload.saveAs(zipPath);
  expect((await readFile(zipPath)).subarray(0, 4).toString("hex")).toBe(
    "504b0304",
  );

  await page.getByRole("button", { name: "Review deletion" }).click();
  await expect(
    page.getByRole("button", { name: "Permanently delete data" }),
  ).toBeDisabled();
  await page.getByLabel("Type DELETE MY JOBS to confirm.").fill("yes");
  await expect(
    page.getByRole("button", { name: "Permanently delete data" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Permanently delete data" }),
  ).toHaveCount(0);
  expect(
    (
      await request.get(`${api}/api/v1/jobs/${job.job_id}`, { headers })
    ).status(),
  ).toBe(200);
  await page.getByRole("button", { name: "Review deletion" }).click();
  await page
    .getByLabel("Type DELETE MY JOBS to confirm.")
    .fill("DELETE MY JOBS");
  await page.getByRole("button", { name: "Permanently delete data" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Job history was deleted." }),
  ).toBeVisible();
  expect(
    (
      await request.get(`${api}/api/v1/jobs/${job.job_id}`, { headers })
    ).status(),
  ).toBe(404);
  await expect(page.getByLabel("CV heading language")).toHaveValue("id");
  await page.getByLabel("What would you like to clear?").selectOption("all");
  await page.getByRole("button", { name: "Review deletion" }).click();
  await page
    .getByLabel("Type DELETE ALL MY DATA to confirm.")
    .fill("DELETE ALL MY DATA");
  await page.getByRole("button", { name: "Permanently delete data" }).click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Your personal workspace data was cleared." }),
  ).toBeVisible();
  await expect(page.getByLabel("CV heading language")).toHaveValue("en");
  expect(
    (await request.get(`${api}/api/v1/career-profile`, { headers })).status(),
  ).toBe(200);
  expect(errors).toEqual([]);
});
