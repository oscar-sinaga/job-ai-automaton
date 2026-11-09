<script lang="ts">
  import { enhance } from "$app/forms";
  import { invalidateAll } from "$app/navigation";
  import type { SubmitFunction } from "@sveltejs/kit";
  import { tick } from "svelte";
  import type { PageProps } from "./$types";
  import { appPath } from "$lib/app-path";
  import type { DeletionPreview } from "$lib/settings";

  let { data, form }: PageProps = $props();
  let busy = $state<string | null>(null);
  let copied = $state("");
  let heldPreview = $state<DeletionPreview | null>(null);
  let dismissedToken = $state("");
  let confirmation = $state("");
  let confirmationInput: HTMLInputElement | undefined = $state();
  const candidatePreview = $derived(
    form?.deleted ? null : (form?.preview ?? heldPreview),
  );
  const preview = $derived(
    candidatePreview?.token !== dismissedToken ? candidatePreview : null,
  );
  const pendingFiles = $derived(
    form?.cleanup?.pending_file_deletions ??
      form?.deleted?.pending_file_deletions ??
      data.settings?.pending_file_deletions ??
      0,
  );

  $effect(() => {
    if (form?.preview) heldPreview = form.preview;
    if (form?.deleted) heldPreview = null;
  });
  $effect(() => {
    if (preview?.token) {
      confirmation = "";
      tick().then(() => confirmationInput?.focus());
    }
  });

  function enhanced(operation: string): SubmitFunction {
    return () => {
      busy = operation;
      return async ({ update, result }) => {
        try {
          await update({
            reset: false,
            invalidateAll: result.type === "success",
          });
        } finally {
          busy = null;
        }
      };
    };
  }

  async function copyApiUrl() {
    try {
      await navigator.clipboard.writeText(data.publicApiUrl);
      copied = "API address copied.";
    } catch {
      copied = "Select the API address below and copy it manually.";
    }
  }

  function countRecords(p: DeletionPreview): number {
    return Object.entries(p.counts).reduce(
      (total, [key, count]) =>
        total +
        (key.startsWith("career_") || key === "application_profiles"
          ? count
          : 0),
      0,
    );
  }
</script>

<svelte:head><title>Settings · OSCAR Job Copilot</title></svelte:head>

<div class="mx-auto max-w-5xl space-y-6 pb-12">
  <header class="flex flex-wrap items-start justify-between gap-4">
    <div class="max-w-2xl">
      <p class="mb-2 text-xs font-semibold tracking-widest text-indigo-700">
        YOUR WORKSPACE
      </p>
      <h1
        class="text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl"
      >
        Settings
      </h1>
      <p class="mt-2 text-sm leading-6 text-slate-600">
        Make each CV start the way you prefer. Connect your tools and stay in
        control of your data.
      </p>
    </div>
    <button
      class="min-h-11 rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
      onclick={() => invalidateAll()}
      disabled={busy !== null}>Refresh status</button
    >
  </header>

  <nav aria-label="Settings sections" class="flex flex-wrap gap-2 text-sm">
    {#each [["cv-defaults", "CV defaults"], ["integrations", "Integrations"], ["your-data", "Your data"]] as [id, label]}
      <a
        href={`#${id}`}
        class="min-h-11 rounded-full border border-slate-200 bg-white px-4 py-3 font-medium text-slate-700 hover:border-indigo-300 hover:text-indigo-700 focus-visible:outline-2 focus-visible:outline-indigo-600"
        >{label}</a
      >
    {/each}
  </nav>

  {#if data.error}<p
      role="alert"
      class="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"
    >
      {data.error}
    </p>{/if}
  {#if form?.error}<p
      role="alert"
      class="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
    >
      {form.error}
    </p>{/if}
  {#if form?.saved}<p
      role="status"
      class="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"
    >
      Settings saved. Your next CV generation will use these defaults.
    </p>{/if}
  {#if form?.deleted}
    <p
      role="status"
      class="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"
    >
      {form.deleted.scope === "jobs"
        ? "Job history was deleted. Your career profile and CV defaults were kept."
        : "Your personal workspace data was cleared. An empty career profile is ready for a fresh start."}
    </p>
  {/if}
  {#if form?.cleanup && pendingFiles === 0}<p
      role="status"
      class="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900"
    >
      Artifact cleanup is complete.
    </p>{/if}
  {#if pendingFiles > 0}
    <div
      role="status"
      class="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950"
    >
      <p>{pendingFiles} artifact file(s) are queued for automatic cleanup.</p>
      <form
        method="POST"
        action="?/retryCleanup"
        use:enhance={enhanced("retryCleanup")}
      >
        <button
          class="min-h-11 rounded-lg border border-amber-400 bg-white px-4 font-medium"
          disabled={busy !== null}>Retry cleanup</button
        >
      </form>
    </div>
  {/if}

  <section
    id="cv-defaults"
    aria-labelledby="cv-heading"
    class="scroll-mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
  >
    <div class="border-b border-slate-100 px-5 py-5 sm:px-6">
      <h2 id="cv-heading" class="text-base font-semibold text-slate-950">
        Your default CV
      </h2>
      <p class="mt-1 text-sm text-slate-600">
        Applied to new generations. Saved CV versions keep their original
        content and presentation.
      </p>
    </div>
    {#if data.settings}
      <form
        method="POST"
        action="?/preferences"
        use:enhance={enhanced("preferences")}
        class="space-y-5 p-5 sm:p-6"
        aria-busy={busy === "preferences"}
      >
        <fieldset disabled={busy !== null} class="grid gap-5 sm:grid-cols-3">
          <label class="space-y-2 text-sm font-medium text-slate-800"
            >CV heading language
            <select
              name="language"
              value={data.settings.default_cv_preferences.language}
              class="min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 font-normal focus:border-indigo-500 focus:outline-2 focus:outline-indigo-500"
              ><option value="en">English</option><option value="id"
                >Bahasa Indonesia</option
              ></select
            >
          </label>
          <label class="space-y-2 text-sm font-medium text-slate-800"
            >PDF layout
            <select
              name="layout"
              value={data.settings.default_cv_preferences.layout}
              class="min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 font-normal focus:border-indigo-500 focus:outline-2 focus:outline-indigo-500"
              ><option value="standard">Standard · easier reading</option
              ><option value="compact">Compact · denser spacing</option></select
            >
          </label>
          <label class="space-y-2 text-sm font-medium text-slate-800"
            >Maximum bullets per role
            <input
              name="max_bullets_per_role"
              type="number"
              min="1"
              max="8"
              step="1"
              required
              value={data.settings.default_cv_preferences.max_bullets_per_role}
              class="min-h-11 w-full rounded-lg border border-slate-300 px-3 font-normal focus:border-indigo-500 focus:outline-2 focus:outline-indigo-500"
            />
          </label>
        </fieldset>
        <p class="rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-600">
          Heading language also guides gap notes. Verified career statements
          stay in their original wording; they are not automatically translated
          or rewritten.
        </p>
        <div class="flex flex-wrap items-center gap-3">
          <button
            class="min-h-11 rounded-lg bg-slate-900 px-5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-60"
            disabled={busy !== null}
            >{busy === "preferences" ? "Saving…" : "Save CV defaults"}</button
          >
          <button
            formaction="?/resetPreferences"
            formnovalidate
            class="min-h-11 rounded-lg px-3 text-sm font-medium text-slate-600 hover:bg-slate-100"
            disabled={busy !== null}>Restore defaults</button
          >
        </div>
      </form>
    {:else}<p class="p-6 text-sm text-slate-600">
        CV settings could not be loaded. Refresh to try again.
      </p>{/if}
  </section>

  <section
    id="integrations"
    aria-labelledby="integration-heading"
    class="scroll-mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
  >
    <div class="border-b border-slate-100 px-5 py-5 sm:px-6">
      <h2
        id="integration-heading"
        class="text-base font-semibold text-slate-950"
      >
        Connected tools
      </h2>
      <p class="mt-1 text-sm text-slate-600">
        AI preferences are saved on the server. Your laptop extension connects
        to this same workspace.
      </p>
    </div>
    <div class="space-y-6 p-5 sm:p-6">
      {#if data.integrations && data.settings}
        <div class="grid gap-3 sm:grid-cols-3">
          {#each [["Backend", "Online", true], ["Database", data.integrations.database_connected ? "Connected" : "Unavailable", data.integrations.database_connected], ["OpenAI", data.integrations.provider_key_configured ? "Key configured" : "Key needed", data.integrations.provider_key_configured]] as [label, value, healthy]}
            <div class="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p class="text-xs font-medium text-slate-600">{label}</p>
              <p
                class="mt-2 flex items-center gap-2 text-sm font-semibold text-slate-900"
              >
                <span
                  class={`size-2 rounded-full ${healthy ? "bg-emerald-600" : "bg-amber-600"}`}
                  aria-hidden="true"
                ></span>{value}
              </p>
            </div>
          {/each}
        </div>
        <form
          method="POST"
          action="?/integrations"
          use:enhance={enhanced("integrations")}
          class="space-y-4"
          aria-busy={busy === "integrations"}
        >
          <fieldset disabled={busy !== null} class="grid gap-4 sm:grid-cols-2">
            <label class="space-y-2 text-sm font-medium text-slate-800"
              >OpenAI model ID
              <input
                name="model"
                value={data.settings.integration_preferences.model ?? ""}
                placeholder={`Server default: ${data.integrations.cv_model}`}
                maxlength="100"
                class="min-h-11 w-full rounded-lg border border-slate-300 px-3 font-normal focus:outline-2 focus:outline-indigo-500"
              />
            </label>
            <label class="space-y-2 text-sm font-medium text-slate-800"
              >Maximum output tokens
              <input
                name="max_output_tokens"
                type="number"
                min="512"
                max="16000"
                step="1"
                placeholder={String(data.integrations.max_output_tokens)}
                value={data.settings.integration_preferences
                  .max_output_tokens ?? ""}
                class="min-h-11 w-full rounded-lg border border-slate-300 px-3 font-normal focus:outline-2 focus:outline-indigo-500"
              />
            </label>
          </fieldset>
          <p class="text-xs leading-5 text-slate-600">
            Leave fields blank to follow server defaults. Current effective
            model: <strong class="font-medium text-slate-800"
              >{data.integrations.cv_model}</strong
            >. Model availability is checked when you generate a CV; a
            configured key alone does not verify access. A larger output limit
            can increase API usage.
          </p>
          <div class="flex flex-wrap gap-3">
            <button
              class="min-h-11 rounded-lg bg-slate-900 px-5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-60"
              disabled={busy !== null}
              >{busy === "integrations"
                ? "Saving…"
                : "Save AI preferences"}</button
            ><button
              formaction="?/resetIntegrations"
              formnovalidate
              class="min-h-11 rounded-lg px-3 text-sm font-medium text-slate-600 hover:bg-slate-100"
              disabled={busy !== null}>Use server defaults</button
            >
          </div>
        </form>
      {:else}<p class="text-sm text-slate-600">
          Integration status is unavailable. Refresh to reconnect.
        </p>{/if}
      <div class="border-t border-slate-100 pt-5">
        <h3 class="text-sm font-semibold text-slate-900">Browser extension</h3>
        <p class="mt-1 text-sm leading-6 text-slate-600">
          In OSCAR extension options, enter this API address and the OSCAR
          application key supplied by your administrator. Provider credentials
          stay on the server.
        </p>
        <label
          class="mt-3 block text-xs font-medium text-slate-600"
          for="extension-api-url">API base URL</label
        >
        <div class="mt-2 flex flex-col gap-2 sm:flex-row">
          <input
            id="extension-api-url"
            readonly
            value={data.publicApiUrl}
            class="min-h-11 min-w-0 flex-1 rounded-lg border border-slate-300 bg-slate-50 px-3 font-mono text-xs text-slate-800"
          /><button
            type="button"
            class="min-h-11 rounded-lg border border-slate-300 px-5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            onclick={copyApiUrl}>Copy address</button
          >
        </div>
        {#if copied}<p class="mt-2 text-xs text-slate-600" role="status">
            {copied}
          </p>{/if}
      </div>
    </div>
  </section>

  <section
    id="your-data"
    aria-labelledby="data-heading"
    class="scroll-mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
  >
    <div class="border-b border-slate-100 px-5 py-5 sm:px-6">
      <h2 id="data-heading" class="text-base font-semibold text-slate-950">
        Your data, your control
      </h2>
      <p class="mt-1 text-sm text-slate-600">
        Keep a portable copy of your career profile, job history, CVs, and
        settings.
      </p>
    </div>
    <div class="p-5 sm:p-6">
      <div
        class="flex flex-col justify-between gap-4 rounded-xl border border-indigo-100 bg-indigo-50/60 p-4 sm:flex-row sm:items-center"
      >
        <div>
          <h3 class="text-sm font-semibold text-slate-900">
            Export your workspace
          </h3>
          <p class="mt-1 max-w-md text-xs leading-5 text-slate-600">
            ZIP includes structured data, saved CV PDFs, and an integrity
            manifest. JSON contains structured data only. Server credentials are
            excluded.
          </p>
        </div>
        <div class="flex shrink-0 flex-wrap gap-2">
          <a
            href={appPath("/settings/export?format=zip")}
            data-sveltekit-reload
            class="inline-flex min-h-11 items-center rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-700"
            >Download ZIP</a
          ><a
            href={appPath("/settings/export?format=json")}
            data-sveltekit-reload
            class="inline-flex min-h-11 items-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >JSON only</a
          >
        </div>
      </div>
      <div class="mt-6 border-t border-slate-100 pt-6">
        <h3 class="text-sm font-semibold text-red-800">
          Delete workspace data
        </h3>
        <p class="mt-2 text-sm leading-6 text-slate-600">
          Choose the scope and review the counts first. Deletion cannot be
          undone from this dashboard. Your account and server connection remain
          available; backups follow their existing retention policy.
        </p>
        <form
          method="POST"
          action="?/preview"
          use:enhance={enhanced("preview")}
          class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end"
        >
          <label
            class="min-w-0 flex-1 space-y-2 text-sm font-medium text-slate-800"
            >What would you like to clear?<select
              name="scope"
              class="min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 font-normal"
              disabled={busy !== null}
              ><option value="jobs"
                >Job history, applications, and generated CVs</option
              ><option value="all"
                >All personal workspace data, including career profile and
                preferences</option
              ></select
            ></label
          >
          <button
            class="min-h-11 rounded-lg border border-red-300 bg-white px-4 text-sm font-semibold text-red-800 hover:bg-red-50 disabled:opacity-60"
            disabled={busy !== null || !data.settings}
            >{busy === "preview"
              ? "Preparing preview…"
              : "Review deletion"}</button
          >
        </form>
        {#if preview}
          <div
            class="mt-5 rounded-xl border border-red-300 bg-red-50 p-4"
            aria-labelledby="delete-confirm-heading"
          >
            <h4
              id="delete-confirm-heading"
              class="text-sm font-semibold text-red-950"
            >
              {preview.scope === "all"
                ? "Clear your personal workspace"
                : "Delete job history"}
            </h4>
            <dl class="my-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              {#each [["Jobs", preview.counts.jobs ?? 0], ["CV versions", preview.counts.cv_versions ?? 0], ["Applications", preview.counts.applications ?? 0], ["Career records", countRecords(preview)]] as [label, count]}<div
                  class="rounded-lg bg-white p-3"
                >
                  <dt class="text-xs text-slate-600">{label}</dt>
                  <dd class="mt-1 text-lg font-semibold text-slate-900">
                    {count}
                  </dd>
                </div>{/each}
            </dl>
            {#if preview.scope === "jobs"}<p class="mb-3 text-xs text-red-900">
                Your career profile and saved preferences will be kept.
              </p>{/if}
            <form
              method="POST"
              action="?/deleteData"
              use:enhance={enhanced("deleteData")}
              class="space-y-3"
            >
              <input type="hidden" name="scope" value={preview.scope} /><input
                type="hidden"
                name="token"
                value={preview.token}
              />
              <label
                for="delete-confirmation"
                class="block text-sm text-red-950"
                >Type <strong class="font-mono"
                  >{preview.confirmation_phrase}</strong
                > to confirm.</label
              >
              <input
                id="delete-confirmation"
                name="confirmation"
                bind:value={confirmation}
                bind:this={confirmationInput}
                autocomplete="off"
                spellcheck="false"
                required
                aria-describedby="delete-expiry"
                class="min-h-11 w-full rounded-lg border border-red-300 bg-white px-3 font-mono text-sm focus:outline-2 focus:outline-red-600"
              />
              <p id="delete-expiry" class="text-xs text-red-900">
                This single-use confirmation expires after five minutes. A
                changed record count requires another preview.
              </p>
              <div class="flex flex-wrap gap-3">
                <button
                  class="min-h-11 rounded-lg bg-red-700 px-4 text-sm font-semibold text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={busy !== null ||
                    confirmation !== preview.confirmation_phrase}
                  >{busy === "deleteData"
                    ? "Deleting…"
                    : "Permanently delete data"}</button
                ><button
                  type="button"
                  class="min-h-11 rounded-lg border border-red-200 bg-white px-4 text-sm font-medium text-slate-700"
                  onclick={() => {
                    dismissedToken = preview?.token ?? "";
                  }}
                  disabled={busy !== null}>Cancel</button
                >
              </div>
            </form>
          </div>
        {/if}
      </div>
    </div>
  </section>
</div>
