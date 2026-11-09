export interface CVPreferences {
  language: "en" | "id";
  layout: "standard" | "compact";
  max_bullets_per_role: number;
}

export interface IntegrationPreferences {
  model: string | null;
  max_output_tokens: number | null;
}

export interface OwnerSettings {
  default_cv_preferences: CVPreferences;
  integration_preferences: IntegrationPreferences;
  updated_at: string | null;
  pending_file_deletions: number;
}

export interface IntegrationStatus {
  backend: "online";
  database_connected: boolean;
  provider: "OpenAI";
  provider_key_configured: boolean;
  cv_model: string;
  max_output_tokens: number;
  api_key_configured: boolean;
  timezone: string;
}

export interface DeletionPreview {
  scope: "jobs" | "all";
  counts: Record<string, number>;
  confirmation_phrase: string;
  token: string;
  expires_at: string;
}

export interface DeletionResult {
  scope: "jobs" | "all";
  deleted_rows: Record<string, number>;
  files_deleted: number;
  pending_file_deletions: number;
}

export interface SettingsActionResult {
  operation: string;
  error?: string;
  saved?: boolean;
  preview?: DeletionPreview;
  deleted?: DeletionResult;
  cleanup?: { files_deleted: number; pending_file_deletions: number };
}

export const DEFAULT_CV_PREFERENCES: CVPreferences = {
  language: "en",
  layout: "standard",
  max_bullets_per_role: 5,
};
