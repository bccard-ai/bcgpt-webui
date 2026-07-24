import { apiClient } from '$lib/apis/client';
import { writable } from 'svelte/store';

// ---------------------------------------------------------------------------
// Skills API client — mirrors bcgpt.agent.routers.skills (mounted /api/v1/skills)
// ---------------------------------------------------------------------------

export interface Skill {
	id: string;
	user_id: string;
	name: string;
	description: string;
	content: string;
	meta: {
		description?: string;
		resources?: Record<string, string>;
		tools?: string[];
		required_capabilities?: string[];
		tags?: string[];
		version?: string;
		source_url?: string;
	};
	is_active: boolean;
	is_global: boolean;
	is_builtin: boolean;
	updated_at: number;
	created_at: number;
}

export interface SkillForm {
	id: string;
	name: string;
	description?: string;
	content?: string;
	meta?: Skill['meta'];
}

/** Catalog of skills shown in the admin page; null until loaded. */
export const skills = writable<Skill[] | null>(null);

export const getSkills = async (token: string = '') =>
	apiClient.get<{ skills: Skill[] }>('/skills/', { token }).then((r) => r.skills ?? []);

export const getSkillById = async (token: string, id: string) =>
	apiClient.get<Skill>(`/skills/${encodeURIComponent(id)}`, { token });

export const createNewSkill = async (token: string, skill: SkillForm) =>
	apiClient.post<Skill>('/skills/', { ...skill }, { token });

export const updateSkillById = async (token: string, id: string, skill: SkillForm) =>
	apiClient.put<Skill>(`/skills/${encodeURIComponent(id)}`, { ...skill }, { token });

export const setSkillFlags = async (
	token: string,
	id: string,
	flags: { is_active?: boolean; is_global?: boolean }
) => apiClient.patch<Skill>(`/skills/${encodeURIComponent(id)}/flags`, { ...flags }, { token });

export const deleteSkillById = async (token: string, id: string) =>
	apiClient.del<{ deleted: string }>(`/skills/${encodeURIComponent(id)}`, { token });

export const importSkillContent = async (token: string, content: string, format: string = 'md') =>
	apiClient.post<Skill>('/skills/import', { content, format }, { token });

export const importSkillFromUrl = async (token: string, url: string) =>
	apiClient.post<Skill>(`/skills/import-url?url=${encodeURIComponent(url)}`, undefined, {
		token
	});

export const exportSkillById = async (token: string, id: string, format: string = 'md') =>
	apiClient.get<{ format: string; content: string }>(
		`/skills/${encodeURIComponent(id)}/export?format=${format}`,
		{ token }
	);
