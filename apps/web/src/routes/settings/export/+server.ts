import { error } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";
import { ApiError, apiRequest } from "$lib/server/api";

export const GET: RequestHandler = async ({ url }) => {
  const format = url.searchParams.get("format") ?? "zip";
  if (!["zip", "json"].includes(format)) error(400, "Choose ZIP or JSON.");
  try {
    const upstream = await apiRequest(`/export?format=${format}`);
    return new Response(upstream.body, {
      headers: {
        "Content-Type":
          upstream.headers.get("content-type") ?? "application/octet-stream",
        "Content-Disposition":
          upstream.headers.get("content-disposition") ??
          `attachment; filename="oscar-export.${format}"`,
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch (e) {
    error(
      e instanceof ApiError ? e.status : 502,
      e instanceof ApiError
        ? e.message
        : "Export is unavailable. Try again shortly.",
    );
  }
};
