<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { toast } from 'svelte-sonner';

	import SkillEditor from '$lib/components/admin/Skill/SkillEditor.svelte';
	import {
		createNewSkill,
		getSkills,
		skills,
		updateSkillById,
		type SkillForm
	} from '$lib/apis/skills';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let current = $state<SkillForm>({
		id: '',
		name: '',
		description: '',
		content: '',
		meta: {}
	});

	onMount(async () => {
		skills.set(await getSkills(localStorage.token));
		const id = new URLSearchParams($page.url.search).get('id');
		if (id) {
			const found = ($skills ?? []).find((s) => s.id === id);
			if (found) current = { ...found };
		}
	});

	const save = async (s: SkillForm) => {
		try {
			const exists = s.id && ($skills ?? []).some((x) => x.id === s.id);
			const payload: SkillForm = {
				...s,
				id: s.id || crypto.randomUUID(),
				meta: s.meta ?? {}
			};
			if (exists) {
				await updateSkillById(localStorage.token, s.id, payload);
			} else {
				await createNewSkill(localStorage.token, payload);
			}
			toast.success($i18n.t('Skill saved'));
			await goto(resolve('/admin/skill'));
		} catch (e) {
			toast.error(`${e}`);
		}
	};
</script>

<div class="mx-auto max-w-3xl p-4">
	<SkillEditor skill={current} {save} />
</div>
