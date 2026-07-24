<script>
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	// Anomalies is now a tab within the Audit panel; keep the deep-link working.
	onMount(() => goto(resolve('/admin/audit?tab=anomalies')));
</script>
