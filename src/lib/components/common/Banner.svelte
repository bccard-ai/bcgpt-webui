<script lang="ts">
	import type { Banner } from '$lib/types';
	import { getContext, onMount } from 'svelte';
	import { fade } from 'svelte/transition';
	import { resolve } from '$app/paths';
	import DOMPurify from 'dompurify';
	import { marked } from 'marked';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * Banner — dismissible notification banner with type-based colouring.
	 *
	 * @example
	 * ```svelte
	 * <Banner {banner} onDismiss={(id) => dismiss(id)} />
	 * ```
	 *
	 * @props banner - Banner data object
	 * @props dismissed - Whether the banner has been dismissed
	 * @props onDismiss - Callback with the banner id when dismissed
	 */
	interface Props {
		/** Banner data object. */
		banner?: Banner;
		/** CSS classes on the outer container. */
		className?: string;
		/** Whether the banner has been dismissed. */
		dismissed?: boolean;
		/** Called with the banner id when dismissed. */
		onDismiss?: (id: string) => void;
	}

	let {
		banner = {
			id: '',
			type: 'info',
			title: '',
			content: '',
			url: '',
			dismissable: true,
			timestamp: Math.floor(Date.now() / 1000)
		},
		className = 'mx-4',
		dismissed = false,
		onDismiss
	}: Props = $props();

	let mounted = $state(false);

	const TYPE_CLASSES: Record<string, string> = {
		info: 'bg-blue-500/20 text-blue-700 dark:text-blue-200 ',
		success: 'bg-green-500/20 text-green-700 dark:text-green-200',
		warning: 'bg-yellow-500/20 text-yellow-700 dark:text-yellow-200',
		error: 'bg-red-500/20 text-red-700 dark:text-red-200'
	};

	const dismiss = (id: string) => {
		dismissed = true;
		onDismiss?.(id);
	};

	onMount(() => {
		mounted = true;
	});
</script>

{#if !dismissed}
	{#if mounted}
		<div
			class="{className} top-0 left-0 right-0 p-2 px-3 flex justify-center items-center relative rounded-xl border border-gray-100 dark:border-gray-850 text-gray-800 dark:text-gary-100 bg-white dark:bg-gray-900 backdrop-blur-xl z-30"
			transition:fade={{ delay: 100, duration: 300 }}
		>
			<div class=" flex flex-col md:flex-row md:items-center flex-1 text-sm w-fit gap-1.5">
				<div class="flex justify-between self-start">
					<div
						class=" text-xs font-bold {TYPE_CLASSES[banner.type] ??
							TYPE_CLASSES['info']}  w-fit px-2 rounded-sm uppercase line-clamp-1 mr-0.5"
					>
						{banner.type}
					</div>

					{#if banner.url}
						<div class="flex md:hidden group w-fit md:items-center">
							<a
								class="text-gray-700 dark:text-white text-xs font-semibold underline"
								href={resolve('/assets/files/whitepaper.pdf' as unknown as '/')}
								target="_blank">{$i18n.t('Learn More')}</a
							>

							<div
								class=" ml-1 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-white"
							>
								<svg
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 16 16"
									fill="currentColor"
									class="w-4 h-4"
								>
									<path
										fill-rule="evenodd"
										d="M4.22 11.78a.75.75 0 0 1 0-1.06L9.44 5.5H5.75a.75.75 0 0 1 0-1.5h5.5a.75.75 0 0 1 .75.75v5.5a.75.75 0 0 1-1.5 0V6.56l-5.22 5.22a.75.75 0 0 1-1.06 0Z"
										clip-rule="evenodd"
									/>
								</svg>
							</div>
						</div>
					{/if}
				</div>

				<div class="flex-1 text-xs text-gray-700 dark:text-white">
					<!-- eslint-disable-next-line svelte/no-at-html-tags -- audited: final rendered HTML is DOMPurify-sanitized (sanitize AFTER marked.parse; order matters) -->
					{@html DOMPurify.sanitize(marked.parse(banner.content))}
				</div>
			</div>

			{#if banner.url}
				<div class="hidden md:flex group w-fit md:items-center">
					<a
						class="text-gray-700 dark:text-white text-xs font-semibold underline"
						href={resolve('/')}
						target="_blank">{$i18n.t('Learn More')}</a
					>

					<div class=" ml-1 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-white">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="size-4"
						>
							<path
								fill-rule="evenodd"
								d="M4.22 11.78a.75.75 0 0 1 0-1.06L9.44 5.5H5.75a.75.75 0 0 1 0-1.5h5.5a.75.75 0 0 1 .75.75v5.5a.75.75 0 0 1-1.5 0V6.56l-5.22 5.22a.75.75 0 0 1-1.06 0Z"
								clip-rule="evenodd"
							/>
						</svg>
					</div>
				</div>
			{/if}
			<div class="flex self-start">
				{#if banner.dismissible}
					<button
						onclick={() => {
							dismiss(banner.id);
						}}
						class="  -mt-1 -mb-2 -translate-y-[1px] ml-1.5 mr-1 text-gray-400 dark:hover:text-white"
						>&times;</button
					>
				{/if}
			</div>
		</div>
	{/if}
{/if}
