// Shared between content.ts and background.ts. Kept minimal and independent of
// the API's own schemas (apps/api/.../jobs/schemas.py) -- this is not a shared
// package, just two small bundles that both need the same shape.

export type ExtractorUsed = 'selection' | 'main' | 'densest_block' | 'body_fallback' | 'none';

export interface ExtractionResult {
	text: string;
	extractor: ExtractorUsed;
	truncated: boolean;
	jobTitle?: string;
	companyName?: string;
}

export interface CaptureOutcome {
	ok: boolean;
	ref?: string;
	captureCompleteness?: string;
	isDuplicate?: boolean;
	error?: string;
}
