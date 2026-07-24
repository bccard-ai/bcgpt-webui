import { apiClient } from '$lib/apis/client';
import { getUserPosition } from '$lib/utils';
import { logger } from '$lib/utils/logger';

export const getUserGroups = async (token: string) => apiClient.get('/users/groups', { token });

export const getUserDefaultPermissions = async (token: string) =>
	apiClient.get('/users/default/permissions', { token });

export const updateUserDefaultPermissions = async (token: string, permissions: object) =>
	apiClient.post('/users/default/permissions', { ...permissions }, { token });

export const updateUserRole = async (token: string, id: string, role: string) =>
	apiClient.post('/users/update/role', { id, role }, { token });

export const getUsers = async (token: string) => {
	const res = await apiClient.get('/users/', { token });
	return res ? res : [];
};

export const getUserSettings = async (token: string) =>
	apiClient.get('/users/user/settings', { token });

export const updateUserSettings = async (token: string, settings: object) =>
	apiClient.post('/users/user/settings/update', { ...settings }, { token });

export const getUserById = async (token: string, userId: string) =>
	apiClient.get(`/users/${userId}`, { token });

export const getUserInfo = async (token: string) => apiClient.get('/users/user/info', { token });

export const updateUserInfo = async (token: string, info: object) =>
	apiClient.post('/users/user/info/update', { ...info }, { token });

export const getAndUpdateUserLocation = async (token: string) => {
	const location = await getUserPosition().catch((err) => {
		logger.error(
			'users',
			'Get And Update User Location failed',
			err instanceof Error ? err : undefined,
			err
		);
		return null;
	});

	if (location) {
		await updateUserInfo(token, { location: location });
		return location;
	} else {
		logger.error('users', 'Failed to get user location');
		return null;
	}
};

export const deleteUserById = async (token: string, userId: string) =>
	apiClient.del(`/users/${userId}`, undefined, { token });

type UserUpdateForm = {
	profile_image_url: string;
	email: string;
	name: string;
	password: string;
};

export const updateUserById = async (token: string, userId: string, user: UserUpdateForm) =>
	apiClient.post(
		`/users/${userId}/update`,
		{
			profile_image_url: user.profile_image_url,
			email: user.email,
			name: user.name,
			password: user.password !== '' ? user.password : undefined
		},
		{ token }
	);
