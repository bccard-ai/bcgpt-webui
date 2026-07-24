<script lang="ts">
	import { getContext } from 'svelte';
	import { agentAutonomyLevels, DEFAULT_AUTONOMY_LEVEL } from '$lib/stores/agent';
	import type { AgentAutonomyLevel } from '$lib/stores/agent';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface Props {
		autonomyLevel?: AgentAutonomyLevel;
	}

	let { autonomyLevel = $bindable(DEFAULT_AUTONOMY_LEVEL) }: Props = $props();

	let selected = $derived($agentAutonomyLevels.find((l) => l.value === autonomyLevel));
</script>

<div>
	<div class="flex w-full justify-between mb-1">
		<div class="self-center text-sm font-semibold">{$i18n.t('Agent Autonomy')}</div>
	</div>

	<div class="flex items-center gap-2">
		<select
			class="w-full rounded-lg text-sm bg-transparent dark:bg-gray-900 outline-hidden border border-gray-100 dark:border-gray-800 py-1.5 px-2"
			bind:value={autonomyLevel}
		>
			{#each $agentAutonomyLevels as level (level.value)}
				<option value={level.value}>{$i18n.t(level.label)}</option>
			{/each}
		</select>
	</div>

	{#if selected}
		<div class="text-xs text-gray-500 mt-1">
			{$i18n.t(selected.description)}
		</div>
	{/if}

	{#if autonomyLevel === 'operator'}
		<div
			class="mt-2 text-xs rounded-lg px-3 py-2 bg-yellow-500/10 text-yellow-700 dark:text-yellow-200"
		>
			⚠️ {$i18n.t(
				'Operator mode lets the agent call tools autonomously (ReAct loop). This can increase latency and cost.'
			)}
		</div>
	{/if}
</div>
