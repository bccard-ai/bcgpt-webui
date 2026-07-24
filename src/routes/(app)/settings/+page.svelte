<!-- BCGPT WebUI - Settings Redirect: Redirects to general settings tab -->
<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';

	onMount(() => {
		goto(resolve('/settings/general'));
	});
</script>
