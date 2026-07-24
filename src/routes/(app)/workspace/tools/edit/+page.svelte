<!-- BCGPT WebUI - Workspace Tool Edit: Edit existing tool with version validation -->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { getToolById, getTools, updateToolById } from '$lib/apis/tools';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ToolkitEditor from '$lib/components/workspace/Tools/ToolkitEditor.svelte';
	import { APP_VERSION } from '$lib/constants';
	import { tools } from '$lib/stores';
	import { compareVersion, extractFrontmatter } from '$lib/utils';
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let tool = $state(null);

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

		const res = await updateToolById('', tool.id, {
			id: data.id,
			name: data.name,
			meta: data.meta,
			content: data.content,
			access_control: data.access_control
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t('Tool updated successfully'));
			tools.set(await getTools(''));

			// await goto('/workspace/tools');
		}
	};

	onMount(async () => {
		const id = page.url.searchParams.get('id');

		if (id) {
			tool = await getToolById('', id).catch((error) => {
				toast.error(`${error}`);
				goto(resolve('/workspace/tools'));
				return null;
			});
		}
	});
</script>

{#if tool}
	<ToolkitEditor
		edit={true}
		id={tool.id}
		name={tool.name}
		meta={tool.meta}
		content={tool.content}
		accessControl={tool.access_control}
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
