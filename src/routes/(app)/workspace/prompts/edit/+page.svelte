<!-- BCGPT WebUI - Workspace Prompt Edit: Edit existing prompt template -->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { prompts } from '$lib/stores';
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { getPromptByCommand, getPrompts, updatePromptByCommand } from '$lib/apis/prompts';
	import { page } from '$app/state';

	import PromptEditor from '$lib/components/workspace/Prompts/PromptEditor.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	let prompt = $state(null);
	const onSubmit = async (_prompt) => {
		const prompt = await updatePromptByCommand('', _prompt).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (prompt) {
			toast.success($i18n.t('Prompt updated successfully'));
			await prompts.set(await getPrompts(''));
			await goto(resolve('/workspace/prompts'));
		}
	};

	onMount(async () => {
		const command = page.url.searchParams.get('command');
		if (command) {
			const _prompt = await getPromptByCommand('', command.replace(/\//g, '')).catch((error) => {
				toast.error(`${error}`);
				return null;
			});

			if (_prompt) {
				prompt = {
					title: _prompt.title,
					command: _prompt.command,
					content: _prompt.content,
					access_control: _prompt?.access_control ?? null
				};
			} else {
				goto(resolve('/workspace/prompts'));
			}
		} else {
			goto(resolve('/workspace/prompts'));
		}
	});
</script>

{#if prompt}
	<PromptEditor {prompt} {onSubmit} edit />
{/if}
