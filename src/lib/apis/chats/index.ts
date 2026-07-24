import { apiClient } from '$lib/apis/client';
import { getTimeRange } from '$lib/utils';

export interface ChatSearchResult {
	id: string;
	title: string;
	updated_at: number;
	created_at: number;
	match_message_id: string | null;
	match_role: 'user' | 'assistant' | null;
	match_snippet: string | null;
}

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export const createNewChat = async (token: string, chat: object) => {
	return apiClient.post('/chats/new', { chat }, { token });
};

export const importChat = async (
	token: string,
	chat: object,
	meta: object | null,
	pinned?: boolean,
	folderId?: string | null
) => {
	return apiClient.post(
		'/chats/import',
		{ chat, meta: meta ?? {}, pinned, folder_id: folderId },
		{ token }
	);
};

export const updateChatEntryInList = (
	chatList: Record<string, unknown>[] | null,
	chatId: string,
	updates: Record<string, unknown>
): Record<string, unknown>[] | null => {
	if (!chatList) return chatList;
	const idx = chatList.findIndex((c) => c.id === chatId);
	if (idx === -1) return chatList;
	const updated = {
		...chatList[idx],
		...updates,
		time_range: getTimeRange((updates.updated_at as string) || (chatList[idx].updated_at as string))
	};
	const newList = [...chatList];
	newList[idx] = updated;
	return newList;
};

// ---------------------------------------------------------------------------
// Listing
// ---------------------------------------------------------------------------

export const getChatList = async (token: string = '', page: number | null = null) => {
	const searchParams = new URLSearchParams();
	if (page !== null) {
		searchParams.append('page', `${page}`);
	}
	const res = await apiClient.get<Record<string, unknown>[]>(`/chats/?${searchParams.toString()}`, {
		token
	});
	return res.map((chat) => ({
		...chat,
		time_range: getTimeRange(chat.updated_at as string | number)
	}));
};

export const getChatListByUserId = async (token: string = '', userId: string) => {
	const res = await apiClient.get<Record<string, unknown>[]>(`/chats/list/user/${userId}`, {
		token
	});
	return res.map((chat) => ({
		...chat,
		time_range: getTimeRange(chat.updated_at as string | number)
	}));
};

export const getArchivedChatList = async (token: string = '') => {
	return apiClient.get('/chats/archived', { token });
};

export const getAllChats = async (token: string) => {
	return apiClient.get('chats/all', { token });
};

export const getChatListBySearchText = async (token: string, text: string, page: number = 1) => {
	const searchParams = new URLSearchParams();
	searchParams.append('text', text);
	searchParams.append('page', `${page}`);
	const res = await apiClient.get<ChatSearchResult[]>(`/chats/search?${searchParams.toString()}`, {
		token
	});
	return res.map((chat) => ({
		...chat,
		time_range: getTimeRange(chat.updated_at as string | number)
	}));
};

export const getChatsByFolderId = async (token: string, folderId: string) => {
	return apiClient.get(`/chats/folder/${folderId}`, { token });
};

export const getAllArchivedChats = async (token: string) => {
	return apiClient.get('/chats/all/archived', { token });
};

export const getAllUserChats = async (token: string) => {
	return apiClient.get('/chats/all/db', { token });
};

export const getAllTags = async (token: string) => {
	return apiClient.get('/chats/all/tags', { token });
};

export const getPinnedChatList = async (token: string = '') => {
	const res = await apiClient.get<Record<string, unknown[]>[]>('/chats/pinned', { token });
	return res.map((chat) => ({
		...chat,
		time_range: getTimeRange(chat.updated_at as string | number)
	}));
};

export const getChatListByTagName = async (token: string = '', tagName: string) => {
	const res = await apiClient.post<Record<string, unknown>[]>(
		'/chats/tags',
		{ name: tagName },
		{ token }
	);
	return res.map((chat) => ({
		...chat,
		time_range: getTimeRange(chat.updated_at as string | number)
	}));
};

// ---------------------------------------------------------------------------
// Single chat operations
// ---------------------------------------------------------------------------

export const getChatById = async (token: string, id: string) => {
	return apiClient.get(`chats/${id}`, { token });
};

export const getChatByShareId = async (token: string, share_id: string) => {
	return apiClient.get(`/chats/share/${share_id}`, { token });
};

export const getChatPinnedStatusById = async (token: string, id: string) => {
	return apiClient.get(`/chats/${id}/pinned`, { token });
};

export const toggleChatPinnedStatusById = async (token: string, id: string) => {
	return apiClient.post(`/chats/${id}/pin`, undefined, { token });
};

export const cloneChatById = async (token: string, id: string, title?: string) => {
	return apiClient.post(`/chats/${id}/clone`, { ...(title && { title }) }, { token });
};

export const cloneSharedChatById = async (token: string, id: string) => {
	return apiClient.post(`/chats/${id}/clone/shared`, undefined, { token });
};

export const shareChatById = async (token: string, id: string) => {
	return apiClient.post(`chats/${id}/share`, undefined, { token });
};

export const updateChatFolderIdById = async (token: string, id: string, folderId?: string) => {
	return apiClient.post(`/chats/${id}/folder`, { folder_id: folderId }, { token });
};

export const archiveChatById = async (token: string, id: string) => {
	return apiClient.post(`/chats/${id}/archive`, undefined, { token });
};

export const deleteSharedChatById = async (token: string, id: string) => {
	return apiClient.del(`/chats/${id}/share`, undefined, { token });
};

export const updateChatById = async (token: string, id: string, chat: object) => {
	return apiClient.post(`/chats/${id}`, { chat }, { token });
};

export const deleteChatById = async (token: string, id: string) => {
	return apiClient.del(`chats/${id}`, undefined, { token });
};

// ---------------------------------------------------------------------------
// Tags
// ---------------------------------------------------------------------------

export const getTagsById = async (token: string, id: string) => {
	const chatId = id.trim();
	// A chat can briefly be unmounted while navigation/auth recovery is in
	// progress. Do not turn that transient state into a request for
	// `/chats//tags`, which Vite handles as its HTML fallback.
	if (!chatId) return [];

	return apiClient.get(`/chats/${encodeURIComponent(chatId)}/tags`, { token });
};

export const addTagById = async (token: string, id: string, tagName: string) => {
	return apiClient.post(`/chats/${id}/tags`, { name: tagName }, { token });
};

export const deleteTagById = async (token: string, id: string, tagName: string) => {
	return apiClient.del(`/chats/${id}/tags`, { name: tagName }, { token });
};

export const deleteTagsById = async (token: string, id: string) => {
	return apiClient.del(`/chats/${id}/tags/all`, undefined, { token });
};

// ---------------------------------------------------------------------------
// Bulk operations
// ---------------------------------------------------------------------------

export const deleteAllChats = async (token: string) => {
	return apiClient.del('/chats/', undefined, { token });
};

export const archiveAllChats = async (token: string) => {
	return apiClient.post('/chats/archive/all', undefined, { token });
};
