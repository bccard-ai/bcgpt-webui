/*
 * SPDX-FileCopyrightText: 2026 BC Card
 * SPDX-License-Identifier: Apache-2.0
 *
 * Extracted from Chat.svelte as the first .svelte.ts module in the codebase.
 * Demonstrates the Svelte 5 pattern for extracting reactive logic out of
 * god-components into testable, focused modules. Future controller extractions
 * (useChatStreaming, useChatHistory, etc.) should follow this same shape.
 */

import { processWeb, processYoutubeVideo } from '$lib/apis/retrieval';

interface FileItem {
	type: string;
	name: string;
	collection_name: string;
	status: string;
	url: string;
	error: string;
	file?: Record<string, unknown>;
	context?: string;
	[key: string]: unknown;
}

interface CreateChatUploadsConfig {
	getFiles: () => FileItem[];
	setFiles: (updater: (prev: FileItem[]) => FileItem[]) => void;
	toastError: (msg: string) => void;
}

export function createChatUploads(config: CreateChatUploadsConfig) {
	const uploadWeb = async (url: string): Promise<void> => {
		const fileItem: FileItem = {
			type: 'doc',
			name: url,
			collection_name: '',
			status: 'uploading',
			url,
			error: ''
		};

		try {
			config.setFiles((prev) => [...prev, fileItem]);
			const res = await processWeb('', '', url);

			if (res) {
				fileItem.status = 'uploaded';
				fileItem.collection_name = res.collection_name;
				fileItem.file = { ...res.file, ...fileItem.file };
				config.setFiles((prev) => [...prev]);
			}
		} catch (e) {
			config.setFiles((prev) => prev.filter((f) => f.name !== url));
			config.toastError(JSON.stringify(e));
		}
	};

	const uploadYoutubeTranscription = async (url: string): Promise<void> => {
		const fileItem: FileItem = {
			type: 'doc',
			name: url,
			collection_name: '',
			status: 'uploading',
			context: 'full',
			url,
			error: ''
		};

		try {
			config.setFiles((prev) => [...prev, fileItem]);
			const res = await processYoutubeVideo('', url);

			if (res) {
				fileItem.status = 'uploaded';
				fileItem.collection_name = res.collection_name;
				fileItem.file = { ...res.file, ...fileItem.file };
				config.setFiles((prev) => [...prev]);
			}
		} catch (e) {
			config.setFiles((prev) => prev.filter((f) => f.name !== url));
			config.toastError(`${e}`);
		}
	};

	return { uploadWeb, uploadYoutubeTranscription };
}
