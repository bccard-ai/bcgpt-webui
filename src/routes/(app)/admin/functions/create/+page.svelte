<!-- BCGPT WebUI - Admin Function Create: New custom function editor -->
<script lang="ts">
	import type { i18n as i18nType } from 'i18next';
	import { get, type Writable } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import { onMount, onDestroy, getContext } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	import { config, functions, models, settings } from '$lib/stores';
	import { createNewFunction, getFunctions } from '$lib/apis/functions';
	import FunctionEditor from '$lib/components/admin/Functions/FunctionEditor.svelte';
	import { getModels } from '$lib/apis';
	import { compareVersion, extractFrontmatter } from '$lib/utils';
	import { APP_VERSION } from '$lib/constants';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let mounted = $state(false);
	let clone = $state(false);
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

		const res = await createNewFunction('', {
			id: data.id,
			name: data.name,
			meta: data.meta,
			content: data.content
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res) {
			toast.success($i18n.t('Function created successfully'));
			functions.set(await getFunctions(''));
			models.set(
				await getModels(
					'',
					get(config)?.features?.enable_direct_connections &&
						(get(settings)?.directConnections ?? null)
				)
			);

			await goto(resolve('/admin/functions'));
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

		func = data;
	};

	onMount(() => {
		window.addEventListener('message', handleMessage);

		if (window.opener ?? false) {
			window.opener.postMessage('loaded', window.location.origin);
		}

		if (sessionStorage.function) {
			func = JSON.parse(sessionStorage.function);
			sessionStorage.removeItem('function');

			clone = true;
		}

		mounted = true;
	});

	onDestroy(() => {
		window.removeEventListener('message', handleMessage);
	});
</script>

{#if mounted}
	{#key func?.content}
		<FunctionEditor
			id={func?.id ?? ''}
			name={func?.name ?? ''}
			meta={func?.meta ?? { description: '' }}
			content={func?.content ?? ''}
			{clone}
			onSave={(value) => {
				saveHandler(value);
			}}
		/>
	{/key}
{/if}
