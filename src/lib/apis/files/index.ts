import { apiClient } from '$lib/apis/client';
import { logger } from '$lib/utils/logger';

// ---------------------------------------------------------------------------
// Upload
// ---------------------------------------------------------------------------

export const uploadFile = async (token: string, file: File, options?: { process?: boolean }) => {
	const data = new FormData();
	data.append('file', file);

	const params = new URLSearchParams();
	if (options?.process !== undefined) {
		params.set('process', String(options.process));
	}
	const path = `/files/${params.toString() ? `?${params.toString()}` : ''}`;
	return apiClient.post(path, data, { token });
};

export const uploadDir = async (token: string) =>
	apiClient.post('/files/upload/dir', undefined, { token });

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

export const getFiles = async (token: string = '') => apiClient.get('/files/', { token });

export const getFileById = async (token: string, id: string) =>
	apiClient.get(`/files/${id}`, { token });

export const updateFileDataContentById = async (token: string, id: string, content: string) =>
	apiClient.post(`/files/${id}/data/content/update`, { content }, { token });

export const getFileContentById = async (id: string) => {
	let error = null;

	const res = await apiClient
		.get<Response>(`/files/${id}/content`, {
			headers: { Accept: 'application/json' },
			rawResponse: true
		})
		.then(async (res) => res.blob())
		.catch((err) => {
			error = err.detail;
			logger.error(
				'files',
				'Get File Content By Id failed',
				err instanceof Error ? err : undefined,
				err
			);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const deleteFileById = async (token: string, id: string) =>
	apiClient.del(`/files/${id}`, undefined, { token });

export const deleteAllFiles = async (token: string) =>
	apiClient.del('/files/all', undefined, { token });
