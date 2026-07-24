/**
 * @fileoverview Store-level type definitions.
 *
 * Extracted from `src/lib/stores/index.ts` to keep store declarations
 * focused on state initialisation and to make types reusable across
 * the codebase without pulling in store subscriptions.
 *
 * @module types/stores
 */

import type { ModelConfig, ModelMeta } from '$lib/apis';

// ── Model types ──────────────────────────────────────────────────────

/** Union of all supported model kinds. */
export type Model = OpenAIModel | OllamaModel;

/** Fields shared by every model variant. */
type BaseModel = {
	/** Unique model identifier (e.g. `'gpt-4o'`, `'llama3:8b'`). */
	id: string;
	/** Human-readable display name. */
	name: string;
	/** Optional model configuration from the backend. */
	info?: ModelConfig;
	/** Optional model metadata (tags, description, etc.). */
	meta?: ModelMeta;
	/** Who owns / serves the model. */
	owned_by: 'ollama' | 'openai' | 'arena';
	/** User-defined tags. */
	tags?: { name: string }[];
	/** Whether this model was created via a direct connection. */
	direct?: boolean;
	/** Whether this model is a preset. */
	preset?: boolean;
	/** Whether this model participates in arena mode. */
	arena?: boolean;
};

/** A model served by an OpenAI-compatible API provider. */
export interface OpenAIModel extends BaseModel {
	owned_by: 'openai';
	/** Whether the model is hosted externally (not self-hosted). */
	external: boolean;
	/** Source identifier for external models. */
	source?: string;
}

/** A model served by a local Ollama instance. */
export interface OllamaModel extends BaseModel {
	owned_by: 'ollama';
	/** Ollama-provided model details (family, quantisation, etc.). */
	details: OllamaModelDetails;
	/** Model file size in bytes. */
	size: number;
	/** Human-readable description. */
	description: string;
	/** Ollama model tag string. */
	model: string;
	/** Last modification timestamp. */
	modified_at: string;
	/** Content digest for caching. */
	digest: string;
	/** Extended Ollama metadata (present when model is pulled). */
	ollama?: {
		name?: string;
		model?: string;
		modified_at: string;
		size?: number;
		digest?: string;
		details?: {
			parent_model?: string;
			format?: string;
			family?: string;
			families?: string[];
			parameter_size?: string;
			quantization_level?: string;
		};
		urls?: number[];
	};
}

/** Hardware / software details reported by Ollama for a model. */
type OllamaModelDetails = {
	parent_model: string;
	format: string;
	family: string;
	families: string[] | null;
	parameter_size: string;
	quantization_level: string;
};

// ── Settings ─────────────────────────────────────────────────────────

/**
 * User preferences persisted across sessions.
 *
 * All fields are optional because the store initialises as `{}`.
 */
export type Settings = {
	/** Selected model IDs for new chats. */
	models?: string[];
	/** Whether multi-turn conversation mode is enabled. */
	conversationMode?: boolean;
	/** Whether speech input auto-sends. */
	speechAutoSend?: boolean;
	/** Whether TTS auto-plays assistant responses. */
	responseAutoPlayback?: boolean;
	/** Audio / STT / TTS configuration. */
	audio?: AudioSettings;
	/** Whether to show the username on messages. */
	showUsername?: boolean;
	/** Whether browser notifications are enabled. */
	notificationEnabled?: boolean;
	/** Auto-title generation settings. */
	title?: TitleSettings;
	/** Whether to split large streaming deltas. */
	splitLargeDeltas?: boolean;
	/** Chat text direction. */
	chatDirection: 'LTR' | 'RTL';
	/** Whether Ctrl+Enter sends the message. */
	ctrlEnterToSend?: boolean;

	// ── Model parameters ──
	/** System prompt override. */
	system?: string;
	/** Request format (e.g. `'json'`). */
	requestFormat?: string;
	/** Ollama keep-alive duration. */
	keepAlive?: string;
	/** Random seed for reproducible outputs. */
	seed?: number;
	/** Sampling temperature. */
	temperature?: string;
	/** Repeat penalty factor. */
	repeat_penalty?: string;
	/** Top-k sampling limit. */
	top_k?: string;
	/** top-p (nucleus) sampling threshold. */
	top_p?: string;
	/** Context window size. */
	num_ctx?: string;
	/** Batch size for processing. */
	num_batch?: string;
	/** Number of tokens to keep from the prompt. */
	num_keep?: string;
	/** Additional model options. */
	options?: ModelOptions;

	// ── UI preferences ──
	/** Whether direct model connections are visible. */
	directConnections?: boolean;
	/** Whether to render chats in bubble style. */
	chatBubble?: boolean;
	/** Whether to use the widescreen layout. */
	widescreenMode?: boolean;
	/** Arbitrary model parameter overrides. */
	params?: Record<string, unknown>;
	/** Whether the rich-text editor is enabled for input. */
	richTextInput?: boolean;
	/** Whether web search is toggled on. */
	webSearch?: boolean;
	/** Whether to upload large text as a file attachment. */
	largeTextAsFile?: boolean;
	/** Maximum image size (px) before compression. */
	imageCompressionSize?: number;
	/** URL of the chat background image. */
	backgroundImageUrl?: string;
	/** Whether to scroll to the branch point on branch switch. */
	scrollOnBranchChange?: boolean;
	/** Whether to include user geolocation in prompts. */
	userLocation?: boolean;
	/** Whether tool servers are enabled. */
	toolServers?: boolean;
	/** Whether to show emoji reactions in voice calls. */
	showEmojiInCall?: boolean;
	/** Whether push notifications are enabled. */
	notifications?: boolean;
	/** Whether image compression is enabled. */
	imageCompression?: boolean;
	/** Whether haptic feedback is enabled on mobile. */
	hapticFeedback?: boolean;
	/** Whether the AI transparency banner is shown. */
	ai_transparency_enabled?: boolean;
	/** Whether voice interruption is allowed during TTS. */
	voiceInterruption?: boolean;
	/** Whether to split large streaming chunks. */
	splitLargeChunks?: boolean;
	/** Whether to show the update toast notification. */
	showUpdateToast?: boolean;
	/** Whether to show the changelog after updates. */
	showChangelog?: boolean;
	/** Whether to auto-copy responses to clipboard. */
	responseAutoCopy?: boolean;
	/** Whether prompt autocomplete suggestions are enabled. */
	promptAutocomplete?: boolean;
	/** Whether to play a sound on new messages. */
	notificationSound?: boolean;
	/** Whether the memory (RAG) feature is enabled. */
	memory?: boolean;
	/** Landing page mode (e.g. `'chat'`, `'workspace'`). */
	landingPageMode?: string;
	/** Whether `<details>` blocks are expanded by default. */
	expandDetails?: boolean;
	/** Whether code blocks are collapsed by default. */
	collapseCodeBlocks?: boolean;
	/** Whether to auto-generate tags for chats. */
	autoTags?: boolean;
	/** Settings schema version. */
	version?: string;
	/** Custom label for AI responses (AI Basic Act compliance). */
	ai_response_label?: string;
	/** Custom notification message for AI interactions. */
	ai_notification_message?: string;
	/** Custom disclaimer text for AI-generated content. */
	ai_disclaimer_text?: string;
};

/** Additional model-level options. */
type ModelOptions = {
	stop?: boolean;
};

/** STT / TTS configuration. */
type AudioSettings = {
	/** Speech-to-text engine identifier. */
	STTEngine?: string;
	/** Text-to-speech engine identifier. */
	TTSEngine?: string;
	/** Selected voice speaker. */
	speaker?: string;
	/** TTS model name. */
	model?: string;
	/** Whether to show non-local voices in the picker. */
	nonLocalVoices?: boolean;
	/** Engine-specific TTS parameters. */
	tts?: {
		voice?: string;
		speed?: number;
		[key: string]: unknown;
	};
	[key: string]: unknown;
};

/** Auto-title generation configuration. */
type TitleSettings = {
	/** Whether automatic title generation is enabled. */
	auto?: boolean;
	/** Model used for local (Ollama) title generation. */
	model?: string;
	/** Model used for external (OpenAI) title generation. */
	modelExternal?: string;
	/** Prompt template for title generation. */
	prompt?: string;
};

// ── Prompt / Document ────────────────────────────────────────────────

/** A saved prompt template. */
export type Prompt = {
	/** Slash-command trigger (e.g. `'/translate'`). */
	command: string;
	/** Owner user ID. */
	user_id: string;
	/** Display title. */
	title: string;
	/** Template content with optional `{{…}}` placeholders. */
	content: string;
	/** Creation timestamp (epoch ms). */
	timestamp: number;
};

/** A knowledge base document reference. */
export type Document = {
	/** Vector-store collection this document belongs to. */
	collection_name: string;
	/** Original file name on disk. */
	filename: string;
	/** Unique document name / ID within the collection. */
	name: string;
	/** Human-readable title. */
	title: string;
};

// ── Config ───────────────────────────────────────────────────────────

/** Backend configuration returned by `/api/config`. */
export type Config = {
	/** Whether the backend is reachable and healthy. */
	status: boolean;
	/** Application display name. */
	name: string;
	/** URL of the app logo. */
	logo_url: string;
	/** Backend version string. */
	version: string;
	/** Default locale code (e.g. `'en-US'`). */
	default_locale: string;
	/** Comma-separated default model IDs for new chats. */
	default_models: string;
	/** Suggested prompts shown on the landing page. */
	default_prompt_suggestions: PromptSuggestion[];
	/** Feature flags. */
	features: {
		/** Whether authentication is required. */
		auth: boolean;
		/** Whether trusted-header auth (e.g. Authelia) is enabled. */
		auth_trusted_header: boolean;
		/** Whether API key auth is available. */
		enable_api_key: boolean;
		/** Whether new user sign-up is allowed. */
		enable_signup: boolean;
		/** Whether the email/password login form is shown. */
		enable_login_form: boolean;
		/** Whether LDAP authentication is enabled. */
		enable_ldap?: boolean;
		/** Whether web search is available. */
		enable_web_search?: boolean;
		/** Whether Google Drive file picking is enabled. */
		enable_google_drive_integration: boolean;
		/** Whether OneDrive file picking is enabled. */
		enable_onedrive_integration: boolean;
		/** Whether image generation is available. */
		enable_image_generation: boolean;
		/** Whether admins can export data. */
		enable_admin_export: boolean;
		/** Whether admins can access any chat. */
		enable_admin_chat_access: boolean;
		/** Whether community sharing is enabled. */
		enable_community_sharing: boolean;
		/** Whether autocomplete prompt generation is enabled. */
		enable_autocomplete_generation: boolean;
		/** Whether the Ollama API is enabled. */
		enable_ollama_api?: boolean;
		/** Whether the OpenAI-compatible API is enabled. */
		enable_openai_api?: boolean;
		/** Whether direct model connections are enabled. */
		enable_direct_connections?: boolean;
		/** Whether direct tool connections are enabled. */
		enable_direct_tools?: boolean;
		/** Whether channels are enabled. */
		enable_channels?: boolean;
		/** Whether WebSocket real-time updates are enabled. */
		enable_websocket?: boolean;
		/** Whether message rating is enabled. */
		enable_message_rating?: boolean;
		/** Whether user webhooks are enabled. */
		enable_user_webhooks?: boolean;
		/** Whether context compression is enabled. */
		enable_context_compression?: boolean;
		/** Whether smart query (NLP-enhanced search) is enabled. */
		enable_smart_query?: boolean;
	};
	/** OAuth provider configuration. */
	oauth: {
		providers: {
			[key: string]: string;
		};
	};
	/** Audio engine defaults. */
	audio?: {
		STTEngine?: string;
		TTSEngine?: string;
		speaker?: string;
		model?: string;
		nonLocalVoices?: boolean;
		tts?: {
			voice?: string;
			speed?: number;
			[key: string]: unknown;
		};
		[key: string]: unknown;
	};
	/** File upload limits. */
	file?: {
		/** Maximum upload size in bytes. */
		max_size?: number;
		/** Maximum number of files per upload. */
		max_count?: number;
	};
	/** Whether the onboarding wizard should be shown. */
	onboarding?: boolean;
	/** Whether license metadata is included. */
	license_metadata?: boolean;
};

/** A suggested prompt shown on the landing page. */
type PromptSuggestion = {
	content: string;
	title: [string, string];
};

// ── Session ──────────────────────────────────────────────────────────

/** The currently authenticated user's session data. */
export type SessionUser = {
	/** User UUID. */
	id: string;
	/** User email address. */
	email: string;
	/** Display name. */
	name: string;
	/** Role: `'admin'`, `'user'`, or `'pending'`. */
	role: string;
	/** URL of the user's profile image. */
	profile_image_url: string;
	/** Granular permission flags. */
	permissions: Record<string, boolean>;
	/** JWT bearer token (only present immediately after login). */
	token?: string;
	/** Unix timestamp at which the current session JWT expires. */
	expires_at?: number;
};
