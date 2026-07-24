<script lang="ts">
	import { type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { config, models, settings } from '$lib/stores';

	import { onMount, onDestroy, getContext } from 'svelte';
	import { createNewModel } from '$lib/apis/models';
	import { getModels } from '$lib/apis';

	import ModelEditor from '$lib/components/workspace/Models/ModelEditor.svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	const onSubmit = async (modelInfo) => {
		if (get(models).find((m) => m.id === modelInfo.id)) {
			toast.error(
				`Error: An agent with the ID '${modelInfo.id}' already exists. Please select a different ID to proceed.`
			);
			return;
		}

		if (modelInfo.id === '') {
			toast.error('Error: Agent ID cannot be empty. Please enter a valid ID to proceed.');
			return;
		}

		if (modelInfo) {
			const res = await createNewModel('', {
				...modelInfo,
				meta: {
					...modelInfo.meta,
					profile_image_url: modelInfo.meta.profile_image_url ?? '/static/favicon.png',
					suggestion_prompts: modelInfo.meta.suggestion_prompts
						? modelInfo.meta.suggestion_prompts.filter((prompt) => prompt.content !== '')
						: null
				},
				params: { ...modelInfo.params }
			}).catch((error) => {
				toast.error(`${error}`);
				return null;
			});

			if (res) {
				await models.set(
					await getModels(
						'',
						get(config)?.features?.enable_direct_connections &&
							(get(settings)?.directConnections ?? null)
					)
				);
				toast.success($i18n.t('Agent created successfully!'));
				await goto(resolve('/workspace/agents'));
			}
		}
	};

	let model = $state(null);

	const handleMessage = async (event: MessageEvent) => {
		if (event.origin !== window.location.origin) return;
		if (
			!['https://BCGPT.com', 'https://www.BCGPT.com', 'http://localhost:5173'].includes(
				event.origin
			)
		) {
			return;
		}

		let data;
		try {
			data = JSON.parse(event.data);
		} catch {
			return;
		}

		if (data?.info) {
			data = data.info;
		}

		model = data;
	};

	onMount(async () => {
		window.addEventListener('message', handleMessage);

		if (window.opener ?? false) {
			window.opener.postMessage('loaded', window.location.origin);
		}

		if (sessionStorage.model) {
			model = JSON.parse(sessionStorage.model);
			sessionStorage.removeItem('model');
		}
	});

	onDestroy(() => {
		window.removeEventListener('message', handleMessage);
	});
</script>

{#key model}
	<ModelEditor {model} {onSubmit} />
{/key}
