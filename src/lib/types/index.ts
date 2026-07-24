/**
 * @fileoverview Shared type definitions for the BCGPT WebUI frontend.
 *
 * @module types
 */

/**
 * An announcement or notification banner displayed to users.
 */
export type Banner = {
	/** Unique identifier. */
	id: string;
	/** Banner type (e.g. `'info'`, `'warning'`). */
	type: string;
	/** Optional title displayed in bold. */
	title?: string;
	/** Body content (may include HTML). */
	content: string;
	/** Optional URL the banner links to. */
	url?: string;
	/** Whether the user can dismiss the banner. */
	dismissible?: boolean;
	/** Unix timestamp (ms) when the banner was created. */
	timestamp: number;
};

/**
 * Strategy for splitting TTS audio output.
 */
export enum TTS_RESPONSE_SPLIT {
	/** Split on sentence-ending punctuation. */
	PUNCTUATION = 'punctuation',
	/** Split on paragraph boundaries. */
	PARAGRAPHS = 'paragraphs',
	/** No splitting — return the full content as one part. */
	NONE = 'none'
}
