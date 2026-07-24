<!-- BCGPT WebUI - Workspace Tool Create: New tool editor with version validation -->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { createNewTool, getTools } from '$lib/apis/tools';
	import ToolkitEditor from '$lib/components/workspace/Tools/ToolkitEditor.svelte';
	import { APP_VERSION } from '$lib/constants';
	import { tools } from '$lib/stores';
	import { compareVersion, extractFrontmatter } from '$lib/utils';
	import { onMount, onDestroy, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let mounted = $state(false);
	let clone = $state(false);
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

		const res = await createNewTool('', {
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
			toast.success($i18n.t('Tool created successfully'));
			tools.set(await getTools(''));

			await goto(resolve('/workspace/tools'));
		}
	};

	const handleMessage = async (event: MessageEvent) => {
		if (event.origin !== window.location.origin) return;
		if (
			!['https://BCGPT.com', 'https://www.BCGPT.com', 'http://localhost:9999'].includes(
				event.origin
			)
		)
			return;

		let data;
		try {
			data = JSON.parse(event.data);
		} catch {
			return;
		}

		tool = data;
	};

	onMount(() => {
		window.addEventListener('message', handleMessage);

		if (window.opener ?? false) {
			window.opener.postMessage('loaded', window.location.origin);
		}

		if (sessionStorage.tool) {
			tool = JSON.parse(sessionStorage.tool);
			sessionStorage.removeItem('tool');

			clone = true;
		}

		mounted = true;
	});

	onDestroy(() => {
		window.removeEventListener('message', handleMessage);
	});
</script>

{#if mounted}
	{#key tool?.content}
		<ToolkitEditor
			id={tool?.id ?? ''}
			name={tool?.name ?? ''}
			meta={tool?.meta ?? { description: '' }}
			content={tool?.content ?? ''}
			access_control={null}
			{clone}
			onSave={(value) => {
				saveHandler(value);
			}}
		/>
	{/key}
{/if}
