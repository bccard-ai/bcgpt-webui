<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import CodeEditor from '$lib/components/common/CodeEditor.svelte';
	import type { SkillForm } from '$lib/apis/skills';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let {
		skill = { id: '', name: '', description: '', content: '', meta: {} },
		onSave
	}: {
		skill?: SkillForm;
		onSave?: (s: SkillForm) => void;
	} = $props();

	let name = $state(skill.name ?? '');
	let description = $state(skill.description ?? '');
	let content = $state(
		skill.content ??
			'# New skill\n\nDescribe when the model should use this skill and what to do.\n'
	);
</script>

<div class="flex flex-col gap-3">
	<div>
		<div class="mb-1 text-xs text-gray-500">{$i18n.t('Name')}</div>
		<input class="w-full rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-850" bind:value={name} />
	</div>
	<div>
		<div class="mb-1 text-xs text-gray-500">{$i18n.t('Description')}</div>
		<input
			class="w-full rounded-lg bg-gray-50 px-3 py-2 dark:bg-gray-850"
			bind:value={description}
		/>
	</div>
	<div>
		<div class="mb-1 text-xs text-gray-500">{$i18n.t('Skill body (markdown)')}</div>
		<CodeEditor bind:value={content} />
	</div>
	<div class="flex justify-end">
		<button
			class="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white"
			onclick={() => onSave?.({ ...skill, name, description, content })}
		>
			{$i18n.t('Save')}
		</button>
	</div>
</div>
