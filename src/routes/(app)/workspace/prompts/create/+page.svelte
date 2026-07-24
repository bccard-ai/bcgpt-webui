<!-- BCGPT WebUI - Workspace Prompt Create: New prompt template editor -->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { prompts } from '$lib/stores';
	import { onMount, onDestroy, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { createNewPrompt, getPrompts } from '$lib/apis/prompts';
	import PromptEditor from '$lib/components/workspace/Prompts/PromptEditor.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	let prompt = $state(null);
	const onSubmit = async (_prompt) => {
		const prompt = await createNewPrompt('', _prompt).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (prompt) {
			toast.success($i18n.t('Prompt created successfully'));

			await prompts.set(await getPrompts(''));
			await goto(resolve('/workspace/prompts'));
		}
	};

	const handleMessage = async (event: MessageEvent) => {
		if (event.origin !== window.location.origin) return;
		if (
			!['https://BCGPT.com', 'https://www.BCGPT.com', 'http://localhost:5173'].includes(
				event.origin
			)
		)
			return;

		let _prompt;
		try {
			_prompt = JSON.parse(event.data);
		} catch {
			return;
		}

		prompt = {
			title: _prompt.title,
			command: _prompt.command,
			content: _prompt.content,
			access_control: null
		};
	};

	onMount(async () => {
		window.addEventListener('message', handleMessage);

		if (window.opener ?? false) {
			window.opener.postMessage('loaded', window.location.origin);
		}

		if (sessionStorage.prompt) {
			const _prompt = JSON.parse(sessionStorage.prompt);

			prompt = {
				title: _prompt.title,
				command: _prompt.command,
				content: _prompt.content,
				access_control: null
			};
			sessionStorage.removeItem('prompt');
		}
	});

	onDestroy(() => {
		window.removeEventListener('message', handleMessage);
	});
</script>

{#key prompt}
	<PromptEditor {prompt} {onSubmit} />
{/key}
