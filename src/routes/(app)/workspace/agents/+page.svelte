<script>
	import { get } from 'svelte/store';
	import { onMount } from 'svelte';
	import { config, models, settings } from '$lib/stores';
	import { getModels } from '$lib/apis';
	import Models from '$lib/components/workspace/Models.svelte';

	onMount(async () => {
		await Promise.all([
			(async () => {
				models.set(
					await getModels(
						'',
						get(config)?.features?.enable_direct_connections && (get(settings)?.directConnections ?? null)
					)
				);
			})()
		]);
	});
</script>

{#if $models !== null}
	<Models />
{/if}
