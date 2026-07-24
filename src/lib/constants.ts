/**
 * @fileoverview Application-wide constants and configuration URLs.
 *
 * Centralises every constant used across the BCGPT WebUI frontend,
 * including API endpoint URLs, supported file types, and version info.
 *
 * @module constants
 */

import { browser, dev } from '$app/environment';

// ── Application identity ─────────────────────────────────────────────

/** Human-readable application name. */
export const APP_NAME = 'BCGPT';

// ── URL configuration ─────────────────────────────────────────────────

/**
 * Dev-mode hostname including port (e.g. `localhost:8090`).
 * Empty string in production builds.
 */
export const APP_HOSTNAME = browser ? (dev ? `${location.hostname}:8090` : ``) : '';

/**
 * Base URL for the running application.
 * Always relative (same-origin). In dev, vite.config `server.proxy` forwards
 * /api, /ollama, /openai, /ws to the backend (:8090) — so csrf_token/session
 * cookies stay same-origin and CSRF-protected POSTs (chat create/update) work.
 * (Previously, cross-origin calls to http://localhost:8090 in development prevented CSRF
 * cookies from being sent, causing POST /chats/new 403 → empty ID → /chats/ 405 cascades.)
 */
export const APP_BASE_URL = '';

/** Base URL for all `/api/v1/` REST endpoints. */
export const API_BASE_URL = `${APP_BASE_URL}/api/v1`;

/** Base URL for Ollama-specific API endpoints. */
export const OLLAMA_API_BASE_URL = `${APP_BASE_URL}/ollama`;

/** Base URL for OpenAI-compatible API endpoints. */
export const OPENAI_API_BASE_URL = `${APP_BASE_URL}/openai`;

/** Base URL for audio-related API endpoints. */
export const AUDIO_API_BASE_URL = `${APP_BASE_URL}/api/v1/audio`;

/** Base URL for image-generation API endpoints. */
export const IMAGES_API_BASE_URL = `${APP_BASE_URL}/api/v1/images`;

/** Base URL for retrieval (RAG) API endpoints. */
export const RETRIEVAL_API_BASE_URL = `${APP_BASE_URL}/api/v1/retrieval`;

/** Base URL for agent-related API endpoints. */
export const AGENTS_API_BASE_URL = `${APP_BASE_URL}/api/v1/agents`;

// ── Version information ──────────────────────────────────────────────

declare const VITE_APP_VERSION: string;
declare const VITE_APP_BUILD_HASH: string;

export const APP_VERSION = VITE_APP_VERSION;
export const APP_BUILD_HASH = VITE_APP_BUILD_HASH;

/** Minimum Ollama version required for full feature support. */
export const REQUIRED_OLLAMA_VERSION = '0.1.16';

// ── File upload constraints ──────────────────────────────────────────

/** MIME types accepted for file upload. */
export const SUPPORTED_FILE_TYPE = [
	'application/epub+zip',
	'application/pdf',
	'text/plain',
	'text/csv',
	'text/xml',
	'text/html',
	'text/x-python',
	'text/css',
	'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
	'application/octet-stream',
	'application/x-javascript',
	'text/markdown',
	'audio/mpeg',
	'audio/wav',
	'audio/ogg',
	'audio/x-m4a'
];

/** File extensions accepted for file upload (without leading dot). */
export const SUPPORTED_FILE_EXTENSIONS = [
	'md',
	'rst',
	'go',
	'py',
	'java',
	'sh',
	'bat',
	'ps1',
	'cmd',
	'js',
	'ts',
	'css',
	'cpp',
	'hpp',
	'h',
	'c',
	'cs',
	'htm',
	'html',
	'sql',
	'log',
	'ini',
	'pl',
	'pm',
	'r',
	'dart',
	'dockerfile',
	'env',
	'php',
	'hs',
	'hsc',
	'lua',
	'nginxconf',
	'conf',
	'm',
	'mm',
	'plsql',
	'perl',
	'rb',
	'rs',
	'db2',
	'scala',
	'bash',
	'swift',
	'vue',
	'svelte',
	'doc',
	'docx',
	'pdf',
	'csv',
	'txt',
	'xls',
	'xlsx',
	'pptx',
	'ppt',
	'msg'
];

/** Maximum number of characters allowed in a pasted text block. */
export const PASTED_TEXT_CHARACTER_LIMIT = 1000;

// ── Build-time environment ───────────────────────────────────────────
// Source: https://kit.svelte.dev/docs/modules#$env-static-public
// Only environment variables prefixed with config.kit.env.publicPrefix
// (usually `PUBLIC_`) are exposed to client-side code.
