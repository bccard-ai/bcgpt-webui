<!-- BCGPT WebUI - Admin Function Edit: Edit existing custom function -->
<script>
	import { get } from 'svelte/store';
	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { config, functions, models, settings } from '$lib/stores';
	import { updateFunctionById, getFunctions, getFunctionById } from '$lib/apis/functions';
	import { toast } from 'svelte-sonner';

	import FunctionEditor from '$lib/components/admin/Functions/FunctionEditor.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { getModels } from '$lib/apis';
	import { compareVersion, extractFrontmatter } from '$lib/utils';
	import { APP_VERSION } from '$lib/constants';

	const i18n = getContext('i18n');

	let func = $state(null);

	const saveHandler = async (data) => {
		const manifest = extractFrontmatter(data.content);
		if (compareVersion(manifest?.required_bcgpt_version ?? '0.0.0', APP_VERSION)) {
			toast.error(
				$i18n.t(
					'BCGPT version (v{{BCGPT_VERSION}}) is lower than required version (v{{REQUIRED_VERSION}})',
					{
						BCGPT_VERSION: APP_VERSION,
						REQUIRED_VERSION: manifest?.required_bcgpt_version ?? '0.0.0'
					}
				)
			);
			return;
		}

		const res = await updateFunctionById('', func.id, {
			id: data.id,
			name: data.name,
			meta: data.meta,
			content: data.content
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t('Function updated successfully'));
			functions.set(await getFunctions(''));
			models.set(
				await getModels(
					'',
					get(config)?.features?.enable_direct_connections &&
						(get(settings)?.directConnections ?? null)
				)
			);
		}
	};

	onMount(async () => {
		const id = page.url.searchParams.get('id');

		if (id) {
			func = await getFunctionById('', id).catch((error) => {
				toast.error(`${error}`);
				goto(resolve('/admin/functions'));
				return null;
			});
		}
	});
</script>

{#if func}
	<FunctionEditor
		edit={true}
		id={func.id}
		name={func.name}
		meta={func.meta}
		content={func.content}
		onSave={(value) => {
			saveHandler(value);
		}}
	/>
{:else}
	<div class="flex items-center justify-center h-full">
		<div class=" pb-16">
			<Spinner />
		</div>
	</div>
{/if}
