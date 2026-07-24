<script lang="ts">
	import { getContext } from 'svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import { config } from '$lib/stores';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	let selected = $state('');
</script>

<div class="min-w-[4.5rem] bg-gray-50 dark:bg-gray-950 flex gap-2.5 flex-col pt-8">
	<div class="flex justify-center relative">
		{#if selected === 'home'}
			<div class="absolute top-0 left-0 flex h-full">
				<div class="my-auto rounded-r-lg w-1 h-8 bg-black dark:bg-white"></div>
			</div>
		{/if}

		<Tooltip content={$i18n.t('Home')} placement="right">
			<button
				class=" cursor-pointer {selected === 'home' ? 'rounded-2xl' : 'rounded-full'}"
				onclick={() => {
					selected = 'home';

					if (window.electronAPI) {
						window.electronAPI.load('home');
					}
				}}
			>
				<img
					src={$config?.logo_url || '/static/splash.png'}
					class="size-11 dark:invert p-0.5"
					alt="logo"
					draggable="false"
				/>
			</button>
		</Tooltip>
	</div>

	<div class=" -mt-1 border-[1.5px] border-gray-100 dark:border-gray-900 mx-4"></div>

	<div class="flex justify-center relative group">
		{#if selected === ''}
			<div class="absolute top-0 left-0 flex h-full">
				<div class="my-auto rounded-r-lg w-1 h-8 bg-black dark:bg-white"></div>
			</div>
		{/if}
		<button
			class=" cursor-pointer bg-transparent"
			onclick={() => {
				selected = '';
			}}
		>
			<img
				src={$config?.logo_url || '/static/favicon.png'}
				class="size-10 {selected === '' ? 'rounded-2xl' : 'rounded-full'}"
				alt="logo"
				draggable="false"
			/>
		</button>
	</div>

	<!-- <div class="flex justify-center relative group text-gray-400">
		<button class=" cursor-pointer p-2" onclick={() => {}}>
			<Plus className="size-4" strokeWidth="2" />
		</button>
	</div> -->
</div>
