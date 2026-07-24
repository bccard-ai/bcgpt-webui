<script lang="ts">
	import Info from '$lib/components/icons/Info.svelte';

	/** Props for the Error component - displays an error message banner */
	interface Props {
		/** The error content to display. Strings are shown directly; objects are JSON-serialized. */
		content?: string;
	}

	let { content = '' }: Props = $props();

	/** Safely formats error content for display */
	function formatError(value: string): string {
		return typeof value === 'string' ? value : JSON.stringify(value);
	}
</script>

<div class="flex my-2 gap-2.5 border px-4 py-3 border-red-600/10 bg-red-600/10 rounded-lg">
	<div class="self-start mt-0.5">
		<Info className="size-5 text-red-700 dark:text-red-400" />
	</div>

	<div class="self-center text-sm">
		{formatError(content)}
	</div>
</div>
