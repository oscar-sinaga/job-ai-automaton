// Mirrors the Pydantic schemas in apps/api/src/oscar_api/modules/jobs/schemas.py
// (docs/05_API_DESIGN.md). Kept as plain interfaces, not generated, since the
// surface is still small and changing fast in early milestones.

export type CaptureCompleteness = 'CAPTURED_PARTIAL' | 'CAPTURED_COMPLETE' | 'NEEDS_ENRICHMENT';

export type CaptureMethod = 'extension' | 'manual_url' | 'paste_text' | 'mobile_share';

export type JobStatus =
	| 'SAVED'
	| 'READY_TO_APPLY'
	| 'APPLYING'
	| 'APPLIED'
	| 'ASSESSMENT'
	| 'INTERVIEW'
	| 'FINAL_INTERVIEW'
	| 'OFFER'
	| 'REJECTED'
	| 'WITHDRAWN'
	| 'SKIPPED';

export interface JobSummary {
	id: number;
	ref: string;
	title: string | null;
	company: string | null;
	source: string | null;
	current_status: JobStatus;
	capture_completeness: CaptureCompleteness;
	cv_ready: boolean;
	latest_cv_version: number | null;
	created_at: string;
	is_duplicate: boolean;
}

export interface JobList {
	items: JobSummary[];
	next_cursor: string | null;
}

export interface SnapshotMeta {
	id: number;
	capture_method: CaptureMethod;
	captured_at: string;
	raw_text_length: number;
	page_title: string | null;
}

export interface JobEventOut {
	event_type: string;
	actor: string;
	metadata: Record<string, unknown>;
	occurred_at: string;
}

export interface JobDetail {
	id: number;
	ref: string;
	title: string | null;
	company: string | null;
	source: string | null;
	url: string;
	canonical_url: string | null;
	capture_completeness: CaptureCompleteness;
	current_status: JobStatus;
	duplicate_of_job_id: number | null;
	created_at: string;
	updated_at: string;
	snapshots: SnapshotMeta[];
	events: JobEventOut[];
}

export interface RawSnapshotOut {
	snapshot_id: number;
	raw_text: string | null;
}

// ── Career profile (docs/05 §7, mirrors apps/api/.../career/schemas.py) ──────

export interface Experience {
	id: number;
	company: string;
	title: string;
	location: string | null;
	start_date: string;
	end_date: string | null;
	is_current: boolean;
	description: string | null;
}

export interface Project {
	id: number;
	name: string;
	description: string | null;
	start_date: string | null;
	end_date: string | null;
	link: string | null;
}

export interface Achievement {
	id: number;
	statement: string;
	experience_id: number | null;
	project_id: number | null;
	context: string | null;
	metric_value: string | null;
	metric_verified: boolean;
	skill_tags: string[];
	domain_tags: string[];
	technology_tags: string[];
	verification_status: string;
	notes: string | null;
}

export interface Skill {
	id: number;
	name: string;
	category: string | null;
	years_experience: number | null;
}

export interface Education {
	id: number;
	institution: string;
	degree: string | null;
	field: string | null;
	start_date: string | null;
	end_date: string | null;
}

export interface Certification {
	id: number;
	name: string;
	issuer: string | null;
	issued_date: string | null;
	expires_date: string | null;
}

export interface ApplicationProfile {
	notice_period: string | null;
	salary_expectation: string | null;
	work_authorization: string | null;
	relocation_ok: boolean | null;
	preferred_location: string | null;
	links: Record<string, unknown>;
}

export interface CareerProfile {
	id: number;
	summary: string | null;
	experiences: Experience[];
	projects: Project[];
	achievements: Achievement[];
	skills: Skill[];
	education: Education[];
	certifications: Certification[];
	application_profile: ApplicationProfile;
}

// ── CV (docs/05 §5, mirrors apps/api/.../cv/schemas.py) ──────────────────────

export interface DraftBullet {
	text: string;
	supporting_fact_ids: string[];
}

export interface DraftBlock {
	experience_id?: number;
	project_id?: number;
	bullets: DraftBullet[];
	company?: string;
	title?: string;
	start_date?: string;
	end_date?: string | null;
	is_current?: boolean;
	name?: string;
}

export interface CVSections {
	summary: DraftBullet;
	experience: DraftBlock[];
	projects: DraftBlock[];
	skills: string[];
	missing_requirements: string[];
	source_facts?: Record<string, string>;
	candidate?: Record<string, string>;
}

export interface GroundingRejection {
	text: string;
	reason: string;
}

export interface GroundingReport {
	claims_checked: number;
	claims_rejected: number;
	rejections: GroundingRejection[];
}

export interface CVVersionSummary {
	id: number;
	version_number: number;
	is_submitted: boolean;
	created_at: string;
}

export interface CVVersionOut {
	id: number;
	job_id: number;
	version_number: number;
	label: string;
	summary_text: string | null;
	sections: CVSections;
	is_submitted: boolean;
	is_approved: boolean;
	created_at: string;
}

// ── Analytics (docs/05 §8, docs/10) ──────────────────────────────────────────

export interface KPIs {
	saved: number;
	ready_to_apply: number;
	applied: number;
	assessment: number;
	interview: number;
	final_interview: number;
	offer: number;
	rejected: number;
}

export interface FunnelStage {
	stage: string;
	count: number;
}

export interface Conversion {
	applied_over_saved: number | null;
	assessment_over_applied: number | null;
	interview_over_applied: number | null;
	offer_over_interview: number | null;
	offer_over_applied: number | null;
}

export interface Backlog {
	cv_ready_not_applied: number;
	saved_older_than_5d: number;
	jobs_without_cv: number;
	applications_needing_action: number;
	partial_captures: number;
}

export interface ActionQueueItem {
	label: string;
	count: number;
	href: string;
}

export interface DashboardOut {
	kpis: KPIs;
	funnel: FunnelStage[];
	conversion: Conversion;
	backlog: Backlog;
	action_queue: ActionQueueItem[];
	sample_note: string;
}

export interface TrendPoint {
	bucket: string;
	saved: number;
	applied: number;
	interviews: number;
	offers: number;
}

export interface SourceOrRoleStat {
	name: string;
	saved: number;
	applied: number;
	interview: number;
	applied_rate: number | null;
}

export interface ProductivityOut {
	median_saved_to_cv_ready_days: number | null;
	median_saved_to_applied_days: number | null;
	applications_last_7d: number;
	backlog_size: number;
}

// ── Applications (docs/05 §6) ────────────────────────────────────────────────

export interface ApplicationOut {
	id: number;
	job_id: number;
	submitted_cv_version_id: number | null;
	current_status: JobStatus;
	created_at: string;
}

export interface GenerateCVResponse {
	cv_version_id: number;
	label: string;
	sections: CVSections;
	missing_requirements: string[];
	grounding_report: GroundingReport;
	run: {
		model_name: string;
		prompt_version: string;
		input_tokens: number;
		output_tokens: number;
		latency_ms: number;
	};
}

export interface CaptureResponse {
	job_id: number;
	ref: string;
	capture_completeness: CaptureCompleteness;
	duplicate_of_job_id: number | null;
	snapshot_id: number;
	created: boolean;
}
