<script lang="ts">
	import { getContext } from 'svelte';

	import { APP_VERSION } from '$lib/constants';
	import XMark from '../icons/XMark.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface VersionInfo {
		current: string;
		latest: string;
	}

	interface Props {
		/** Version information containing current and latest version strings */
		version?: VersionInfo;
		/** Callback invoked when the toast is dismissed */
		onClose?: () => void;
	}

	let {
		version = {
			current: APP_VERSION,
			latest: APP_VERSION
		},
		onClose = () => {}
	}: Props = $props();
</script>

<div
	class="flex items-start bg-[#F1F8FE] dark:bg-[#020C1D] border border-[3371D5] dark:border-[#03113B] text-[#3371D5] dark:text-[#6795EC] rounded-lg px-3.5 py-3 text-xs max-w-80 pr-2 w-full shadow-lg"
>
	<div class="flex-1 font-medium">
		{$i18n.t(`A new version (v{{LATEST_VERSION}}) is now available.`, {
			LATEST_VERSION: version.latest
		})}

		<a href="https://github.com/bccard-ai/bcgpt-webui/releases" target="_blank" class="underline">
			{$i18n.t('Update for the latest features and improvements.')}</a
		>
	</div>

	<div class=" shrink-0 pr-1">
		<button
			class=" hover:text-blue-900 dark:hover:text-blue-300 transition"
			onclick={() => {
				onClose?.();
			}}
		>
			<XMark />
		</button>
	</div>
</div>
