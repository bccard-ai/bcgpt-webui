import { apiClient } from '$lib/apis/client';

export const getGravatarUrl = async (token: string, email: string) => {
	return apiClient.get(`/utils/gravatar?email=${email}`, { token });
};

export const formatPythonCode = async (token: string, code: string) => {
	return apiClient.post('/utils/code/format', { code }, { token });
};

export const downloadChatAsPDF = async (token: string, title: string, messages: object[]) => {
	const res = await apiClient.post<Response>(
		'/utils/pdf',
		{ title, messages },
		{
			token,
			rawResponse: true
		}
	);
	return res.blob();
};

export const getHTMLFromMarkdown = async (token: string, md: string) => {
	const res = await apiClient.post<{ html: string }>('/utils/markdown', { md }, { token });
	return res.html;
};

export const downloadDatabase = async (token: string) => {
	const response = await apiClient.get<Response>('/utils/db/download', {
		token,
		rawResponse: true
	});
	const blob = await response.blob();
	const url = window.URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = 'bcgpt.db';
	document.body.appendChild(a);
	a.click();
	window.URL.revokeObjectURL(url);
};

export const downloadLiteLLMConfig = async (token: string) => {
	const response = await apiClient.get<Response>('/utils/litellm/config', {
		token,
		rawResponse: true
	});
	const blob = await response.blob();
	const url = window.URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = 'config.yaml';
	document.body.appendChild(a);
	a.click();
	window.URL.revokeObjectURL(url);
};
