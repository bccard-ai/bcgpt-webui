<script lang="ts">
	import { knowledge, prompts } from '$lib/stores';

	import { removeLastWordFromString } from '$lib/utils';
	import { getPrompts } from '$lib/apis/prompts';
	import { getKnowledgeBases } from '$lib/apis/knowledge';

	import Prompts from './Commands/Prompts.svelte';
	import Knowledge from './Commands/Knowledge.svelte';
	import Models from './Commands/Models.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	interface Props {
		prompt?: string;
		files?: Record<string, unknown>[];
		onSelect?: (...args: unknown[]) => void;
		onUpload?: (...args: unknown[]) => void;
	}

	let {
		prompt = $bindable(''),
		files = $bindable([]),
		onSelect = () => {},
		onUpload = () => {}
	}: Props = $props();

	let loading = $state(false);
	let commandElement = $state(null);

	export const selectUp = () => {
		commandElement?.selectUp();
	};

	export const selectDown = () => {
		commandElement?.selectDown();
	};

	let command = $derived(prompt?.split('\n').pop()?.split(' ')?.pop() ?? '');

	let show = $derived(
		['/', '#', '@'].includes(command?.charAt(0)) || '\\#' === command.slice(0, 2)
	);

	const init = async () => {
		loading = true;
		await Promise.all([
			(async () => {
				prompts.set(await getPrompts(''));
			})(),
			(async () => {
				knowledge.set(await getKnowledgeBases(''));
			})()
		]);
		loading = false;
	};

	$effect(() => {
		if (show) {
			init();
		}
	});
</script>

{#if show}
	{#if !loading}
		{#if command?.charAt(0) === '/'}
			<Prompts bind:this={commandElement} bind:prompt bind:files {command} />
		{:else if (command?.charAt(0) === '#' && command.startsWith('#') && !command.includes('# ')) || ('\\#' === command.slice(0, 2) && command.startsWith('#') && !command.includes('# '))}
			<Knowledge
				bind:this={commandElement}
				bind:prompt
				command={command.includes('\\#') ? command.slice(2) : command}
				onYoutube={(e: unknown) => {
					onUpload({
						type: 'youtube',
						data: (e as CustomEvent)?.detail
					});
				}}
				onUrl={(e: unknown) => {
					onUpload({
						type: 'web',
						data: (e as CustomEvent)?.detail
					});
				}}
				onSelect={(e: unknown) => {
					const detail = (e as CustomEvent)?.detail;
					if (files.find((f) => f.id === detail.id)) {
						return;
					}

					files = [
						...files,
						{
							...detail,
							status: 'processed'
						}
					];

					onSelect?.();
				}}
			/>
		{:else if command?.charAt(0) === '@'}
			<Models
				bind:this={commandElement}
				{command}
				onSelect={(e: unknown) => {
					prompt = removeLastWordFromString(prompt, command);

					onSelect({
						type: 'model',
						data: (e as CustomEvent)?.detail
					});
				}}
			/>
		{/if}
	{:else}
		<div
			id="commands-container"
			class="px-2 mb-2 text-left w-full absolute bottom-0 left-0 right-0 z-10"
		>
			<div class="flex w-full rounded-xl border border-gray-100 dark:border-gray-850">
				<div
					class="max-h-60 flex flex-col w-full rounded-xl bg-white dark:bg-gray-900 dark:text-gray-100"
				>
					<Spinner />
				</div>
			</div>
		</div>
	{/if}
{/if}
