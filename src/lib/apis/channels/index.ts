import { apiClient } from '$lib/apis/client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ChannelForm = {
	name: string;
	data?: object;
	meta?: object;
	access_control?: object;
};

type MessageForm = {
	parent_id?: string;
	content: string;
	data?: object;
	meta?: object;
};

// ---------------------------------------------------------------------------
// Channel CRUD
// ---------------------------------------------------------------------------

export const createNewChannel = async (token: string = '', channel: ChannelForm) => {
	return apiClient.post('/channels/create', { ...channel }, { token });
};

export const getChannels = async (token: string = '') => {
	return apiClient.get('/channels/', { token });
};

export const getChannelById = async (token: string = '', channel_id: string) => {
	return apiClient.get(`/channels/${channel_id}`, { token });
};

export const updateChannelById = async (
	token: string = '',
	channel_id: string,
	channel: ChannelForm
) => {
	return apiClient.post(`/channels/${channel_id}/update`, { ...channel }, { token });
};

export const deleteChannelById = async (token: string = '', channel_id: string) => {
	return apiClient.del(`/channels/${channel_id}/delete`, undefined, { token });
};

// ---------------------------------------------------------------------------
// Messages
// ---------------------------------------------------------------------------

export const getChannelMessages = async (
	token: string = '',
	channel_id: string,
	skip: number = 0,
	limit: number = 50
) => {
	return apiClient.get(`/channels/${channel_id}/messages?skip=${skip}&limit=${limit}`, { token });
};

export const getChannelThreadMessages = async (
	token: string = '',
	channel_id: string,
	message_id: string,
	skip: number = 0,
	limit: number = 50
) => {
	return apiClient.get(
		`/channels/${channel_id}/messages/${message_id}/thread?skip=${skip}&limit=${limit}`,
		{ token }
	);
};

export const sendMessage = async (token: string = '', channel_id: string, message: MessageForm) => {
	return apiClient.post(`/channels/${channel_id}/messages/post`, { ...message }, { token });
};

export const updateMessage = async (
	token: string = '',
	channel_id: string,
	message_id: string,
	message: MessageForm
) => {
	return apiClient.post(
		`/channels/${channel_id}/messages/${message_id}/update`,
		{ ...message },
		{ token }
	);
};

// ---------------------------------------------------------------------------
// Reactions
// ---------------------------------------------------------------------------

export const addReaction = async (
	token: string = '',
	channel_id: string,
	message_id: string,
	name: string
) => {
	return apiClient.post(
		`/channels/${channel_id}/messages/${message_id}/reactions/add`,
		{ name },
		{ token }
	);
};

export const removeReaction = async (
	token: string = '',
	channel_id: string,
	message_id: string,
	name: string
) => {
	return apiClient.post(
		`/channels/${channel_id}/messages/${message_id}/reactions/remove`,
		{ name },
		{ token }
	);
};

export const deleteMessage = async (token: string = '', channel_id: string, message_id: string) => {
	return apiClient.del(`/channels/${channel_id}/messages/${message_id}/delete`, undefined, {
		token
	});
};
