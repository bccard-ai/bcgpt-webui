<script>
	import { onMount } from 'svelte';
	import { getSkills, skills } from '$lib/apis/skills';
	import SkillsManager from '$lib/components/admin/Skill/Skills.svelte';
	import Breadcrumb from '$lib/components/common/Breadcrumb.svelte';

	onMount(async () => {
		skills.set(await getSkills(localStorage.token));
	});
</script>

{#if $skills !== null}
	<Breadcrumb items={[{ label: 'Skills' }]} />
	<SkillsManager />
{/if}
