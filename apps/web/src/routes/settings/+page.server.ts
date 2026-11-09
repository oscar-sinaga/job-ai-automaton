import { fail, type ActionFailure } from "@sveltejs/kit";
import type { Actions, PageServerLoad } from "./$types";
import { appPath } from "$lib/app-path";
import { ApiError, apiFetch } from "$lib/server/api";
import {
  DEFAULT_CV_PREFERENCES,
  type DeletionPreview,
  type DeletionResult,
  type IntegrationStatus,
  type OwnerSettings,
  type SettingsActionResult,
} from "$lib/settings";

export const load: PageServerLoad = async ({ url, setHeaders }) => {
  setHeaders({ "cache-control": "no-store" });
  const [settings, integrations] = await Promise.allSettled([
    apiFetch<OwnerSettings>("/settings"),
    apiFetch<IntegrationStatus>("/settings/integrations"),
  ]);
  return {
    settings: settings.status === "fulfilled" ? settings.value : null,
    integrations:
      integrations.status === "fulfilled" ? integrations.value : null,
    publicApiUrl: new URL(appPath("/api/v1"), url.origin).href,
    error:
      settings.status === "rejected" || integrations.status === "rejected"
        ? "Some settings are unavailable. Refresh to reconnect before making changes."
        : null,
  };
};

async function run(
  operation: string,
  fn: () => Promise<Partial<SettingsActionResult>>,
): Promise<SettingsActionResult | ActionFailure<SettingsActionResult>> {
  try {
    return { operation, ...(await fn()) };
  } catch (e) {
    return fail(e instanceof ApiError && e.status < 500 ? e.status : 502, {
      operation,
      error:
        e instanceof ApiError && e.status < 500
          ? e.message
          : "The server could not complete this request. Your change was not confirmed.",
    });
  }
}

export const actions: Actions = {
  preferences: async ({ request }) => {
    const form = await request.formData();
    const language = String(form.get("language"));
    const layout = String(form.get("layout"));
    const bullets = Number(form.get("max_bullets_per_role"));
    if (
      !["en", "id"].includes(language) ||
      !["standard", "compact"].includes(layout) ||
      !Number.isInteger(bullets) ||
      bullets < 1 ||
      bullets > 8
    ) {
      return fail(422, {
        operation: "preferences",
        error: "Choose valid CV options and 1–8 bullets per role.",
      });
    }
    return run("preferences", async () => {
      await apiFetch("/settings", {
        method: "PUT",
        body: JSON.stringify({
          default_cv_preferences: {
            language,
            layout,
            max_bullets_per_role: bullets,
          },
        }),
      });
      return { saved: true };
    });
  },
  resetPreferences: async () =>
    run("resetPreferences", async () => {
      await apiFetch("/settings", {
        method: "PUT",
        body: JSON.stringify({
          default_cv_preferences: DEFAULT_CV_PREFERENCES,
        }),
      });
      return { saved: true };
    }),
  integrations: async ({ request }) => {
    const form = await request.formData();
    const model = String(form.get("model") ?? "").trim() || null;
    const raw = String(form.get("max_output_tokens") ?? "").trim();
    const max_output_tokens = raw ? Number(raw) : null;
    if (
      (model &&
        (model.startsWith("sk-") ||
          !/^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,99}$/.test(model))) ||
      (max_output_tokens !== null &&
        (!Number.isInteger(max_output_tokens) ||
          max_output_tokens < 512 ||
          max_output_tokens > 16000))
    ) {
      return fail(422, {
        operation: "integrations",
        error: "Use a valid model ID and an output limit of 512–16,000 tokens.",
      });
    }
    return run("integrations", async () => {
      await apiFetch("/settings/integrations", {
        method: "PUT",
        body: JSON.stringify({ model, max_output_tokens }),
      });
      return { saved: true };
    });
  },
  resetIntegrations: async () =>
    run("resetIntegrations", async () => {
      await apiFetch("/settings/integrations", {
        method: "PUT",
        body: JSON.stringify({ model: null, max_output_tokens: null }),
      });
      return { saved: true };
    }),
  preview: async ({ request }) => {
    const form = await request.formData();
    return run("preview", async () => ({
      preview: await apiFetch<DeletionPreview>("/settings/data/preview", {
        method: "POST",
        body: JSON.stringify({ scope: form.get("scope") }),
      }),
    }));
  },
  deleteData: async ({ request }) => {
    const form = await request.formData();
    return run("deleteData", async () => ({
      deleted: await apiFetch<DeletionResult>("/settings/data/delete", {
        method: "POST",
        body: JSON.stringify({
          scope: form.get("scope"),
          token: form.get("token"),
          confirmation: form.get("confirmation"),
        }),
      }),
    }));
  },
  retryCleanup: async () =>
    run("retryCleanup", async () => ({
      cleanup: await apiFetch("/settings/files/retry", {
        method: "POST",
        body: "{}",
      }),
    })),
};
