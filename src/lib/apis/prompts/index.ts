import { apiClient } from '$lib/apis/client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type PromptItem = {
	command: string;
	title: string;
	content: string;
	access_control?: null | object;
};

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export const createNewPrompt = async (token: string, prompt: PromptItem) => {
	return apiClient.post('/prompts/create', { ...prompt, command: `/${prompt.command}` }, { token });
};

export const getPrompts = async (token: string = '') => {
	return apiClient.get('/prompts/', { token });
};

export const getPromptList = async (token: string = '') => {
	return apiClient.get('/prompts/list', { token });
};

export const getPromptByCommand = async (token: string, command: string) => {
	return apiClient.get(`/prompts/command/${command}`, { token });
};

export const updatePromptByCommand = async (token: string, prompt: PromptItem) => {
	return apiClient.post(
		`/prompts/command/${prompt.command}/update`,
		{ ...prompt, command: `/${prompt.command}` },
		{ token }
	);
};

export const deletePromptByCommand = async (token: string, command: string) => {
	const normalizedCommand = command.charAt(0) === '/' ? command.slice(1) : command;
	return apiClient.del(`/prompts/command/${normalizedCommand}/delete`, undefined, { token });
};
