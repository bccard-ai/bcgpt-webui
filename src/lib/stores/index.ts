/**
 * @fileoverview Global Svelte stores for application state.
 *
 * Centralises all reactive state used across the BCGPT WebUI frontend.
 * Store types are defined in {@link module:types/stores}.
 *
 * @module stores
 */

import { APP_NAME } from '$lib/constants';
import { type Writable, writable } from 'svelte/store';
import type { Banner } from '$lib/types';
import type { Socket } from 'socket.io-client';

import type { Config, Model, Settings, Prompt, Document, SessionUser } from '$lib/types/stores';

import emojiShortCodes from '$lib/emoji-shortcodes.json';

// ── Backend ───────────────────────────────────────────────────────────

/** Display name of the application (mirrors `APP_NAME` constant). */
export const APP_NAME_STORE = writable(APP_NAME);

/** Backend configuration object, `undefined` until first fetch completes. */
export const config: Writable<Config | undefined> = writable(undefined);

/** Currently authenticated session user, `undefined` when not logged in. */
export const user: Writable<SessionUser | undefined> = writable(undefined);

// ── Electron / Desktop app ────────────────────────────────────────────

/** Whether the app is running inside an Electron wrapper. */
export const isApp = writable(false);

/** Electron app metadata. */
export const appInfo = writable(null);

/** Electron app persistent data. */
export const appData = writable(null);

// ── Model management ──────────────────────────────────────────────────

/** Pool of active model download tasks. */
export const MODEL_DOWNLOAD_POOL = writable({});

/** Available models fetched from backend. */
export const models: Writable<Model[]> = writable([]);

// ── UI state ──────────────────────────────────────────────────────────

/** Whether the viewport is mobile-sized. */
export const mobile = writable(false);

/** WebSocket connection to the backend. */
export const socket: Writable<null | Socket> = writable(null);

/** IDs of users currently active (online). */
export const activeUserIds: Writable<null | string[]> = writable(null);

/** Pool of in-progress API usage requests. */
export const USAGE_POOL: Writable<null | string[]> = writable(null);

/** Active colour theme: `'light'`, `'dark'`, or `'system'`. */
export const theme = writable('system');

/** Reverse lookup map: emoji character → short-code. */
export const shortCodesToEmojis = writable(
	Object.entries(emojiShortCodes).reduce(
		(acc: Record<string, string>, [key, value]) => {
			if (typeof value === 'string') {
				acc[value] = key;
			} else {
				for (const v of value) {
					acc[v] = key;
				}
			}
			return acc;
		},
		{} as Record<string, string>
	)
);

// ── TTS ───────────────────────────────────────────────────────────────

/** Web Worker instance for Kokoro TTS processing. */
export const TTSWorker = writable(null);

// ── Chat state ────────────────────────────────────────────────────────

/** Currently active chat ID. */
export const chatId = writable('');

/** Title of the currently active chat. */
export const chatTitle = writable('');

/** All channels the user has access to. */
export const channels = writable([]);

/** User's chat list (full or paginated). */
export const chats = writable(null);

/** Chats pinned to the top of the sidebar. */
export const pinnedChats = writable([]);

/** User-created tags for organising chats. */
export const tags = writable([]);

// ── Workspace resources ───────────────────────────────────────────────

/** Saved prompt templates. */
export const prompts: Writable<null | Prompt[]> = writable(null);

/** Knowledge base documents. */
export const knowledge: Writable<null | Document[]> = writable(null);

/** Custom tools. */
export const tools = writable(null);

/** Custom functions. */
export const functions = writable(null);

/** External tool server configurations. */
export const toolServers = writable([]);

// ── Banners & settings ────────────────────────────────────────────────

/** Active announcement / notification banners. */
export const banners: Writable<Banner[]> = writable([]);

/** User preferences persisted across sessions. */
export const settings: Writable<Settings> = writable({ chatDirection: 'LTR' });

// ── Panel visibility ──────────────────────────────────────────────────

/** Whether the left sidebar is visible. */
export const showSidebar = writable(false);

/** Whether the settings panel is open. */
export const showSettings = writable(false);

/** Whether the archived-chats view is active. */
export const showArchivedChats = writable(false);

/** Whether the changelog modal is shown. */
export const showChangelog = writable(false);

/** Whether the chat controls panel is open. */
export const showControls = writable(false);

/** Whether the chat overview panel is open. */
export const showOverview = writable(false);

/** Whether the artifacts panel is open. */
export const showArtifacts = writable(false);

/** Whether the voice/video call overlay is shown. */
export const showCallOverlay = writable(false);

// ── Feature flags / modes ─────────────────────────────────────────────

/** Whether temporary (ephemeral) chat mode is active. */
export const temporaryChatEnabled = writable(false);

/** Whether scroll-based pagination is enabled for the chat list. */
export const scrollPaginationEnabled = writable(false);

/** Current page number for paginated chat list. */
export const currentChatPage = writable(1);

/** Whether this browser tab was the most recently active. */
export const isLastActiveTab = writable(true);

/** Whether a notification sound is currently playing. */
export const playingNotificationSound = writable(false);

// ── Re-export store types for downstream consumers ────────────────────
export type { Model, OpenAIModel, OllamaModel } from '$lib/types/stores';
export type { Settings, Config, Prompt, Document, SessionUser } from '$lib/types/stores';
