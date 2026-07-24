<!-- BCGPT WebUI - Backend Error: Displayed when backend server is unreachable -->
<script lang="ts">
	import { type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { get } from 'svelte/store';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { APP_NAME_STORE, config } from '$lib/stores';
	import { onMount, getContext } from 'svelte';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let loaded = $state(false);

	onMount(async () => {
		if (get(config)) {
			await goto(resolve('/'));
		}

		loaded = true;
	});
</script>

{#if loaded}
	<div class="absolute w-full h-full flex z-50">
		<div class="absolute rounded-xl w-full h-full backdrop-blur-sm flex justify-center">
			<div class="m-auto pb-44 flex flex-col justify-center">
				<div class="max-w-md">
					<div class="text-center text-2xl font-medium z-50">
						{$i18n.t('{{appName}} Backend Required', { appName: $APP_NAME_STORE })}
					</div>

					<div class=" mt-4 text-center text-sm w-full">
						{$i18n.t(
							"Oops! You're using an unsupported method (frontend only). Please serve from the backend."
						)}

						<br class=" " />
						<br class=" " />
						<a
							class=" font-semibold underline"
							href="https://github.com/bccard-ai/bcgpt-webui#how-to-install-"
							target="_blank">{$i18n.t('See readme.md for instructions')}</a
						>
					</div>

					<div class=" mt-6 mx-auto relative group w-fit">
						<button
							class="relative z-20 flex px-5 py-2 rounded-full bg-gray-100 hover:bg-gray-200 transition font-medium text-sm"
							onclick={() => {
								location.href = '/';
							}}
						>
							{$i18n.t('Check Again')}
						</button>
					</div>
				</div>
			</div>
		</div>
	</div>
{/if}
