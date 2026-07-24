<script lang="ts">
	import { type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	import { onMount, getContext } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { page } from '$app/state';
	import { config, models, settings } from '$lib/stores';

	import { getModelById, updateModelById } from '$lib/apis/models';

	import { getModels } from '$lib/apis';
	import ModelEditor from '$lib/components/workspace/Models/ModelEditor.svelte';

	let model = $state(null);

	onMount(async () => {
		const _id = page.url.searchParams.get('id');
		if (_id) {
			model = await getModelById('', _id).catch(() => {
				return null;
			});

			if (!model) {
				goto(resolve('/workspace/agents'));
			}
		} else {
			goto(resolve('/workspace/agents'));
		}
	});

	const onSubmit = async (modelInfo) => {
		const res = await updateModelById('', modelInfo.id, modelInfo);

		if (res) {
			await models.set(
				await getModels(
					'',
					get(config)?.features?.enable_direct_connections &&
						(get(settings)?.directConnections ?? null)
				)
			);
			toast.success($i18n.t('Agent updated successfully'));
			await goto(resolve('/workspace/agents'));
		}
	};
</script>

{#if model}
	<ModelEditor edit={true} {model} {onSubmit} />
{/if}
