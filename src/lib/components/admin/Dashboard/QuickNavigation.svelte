<script lang="ts">
	import { resolve } from '$app/paths';
	import { useI18n } from './i18n';
	import DashboardWidget from './DashboardWidget.svelte';
	import UsersSolid from '$lib/components/icons/UsersSolid.svelte';
	import ChartBar from '$lib/components/icons/ChartBar.svelte';
	import Wrench from '$lib/components/icons/Wrench.svelte';
	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import Shield from '$lib/components/icons/Shield.svelte';
	import BookOpen from '$lib/components/icons/BookOpen.svelte';
	import ChevronRight from '$lib/components/icons/ChevronRight.svelte';

	const i18n = useI18n();

	const links = [
		{
			href: '/admin/users',
			icon: 'users',
			label: 'Users',
			desc: 'Manage users, roles and permissions'
		},
		{
			href: '/admin/evaluations',
			icon: 'eval',
			label: 'Evaluations',
			desc: 'View leaderboard and feedback history'
		},
		{
			href: '/admin/functions',
			icon: 'wrench',
			label: 'Functions',
			desc: 'Create and manage custom functions'
		},
		{
			href: '/admin/settings',
			icon: 'cog',
			label: 'Settings',
			desc: 'Configure connections, models and more'
		},
		{
			href: '/admin/audit',
			icon: 'shield',
			label: 'Audit',
			desc: 'Audit logs and security events'
		},
		{ href: '/admin/rag', icon: 'book', label: 'Knowledge', desc: 'Vector database and documents' }
	];
</script>

<DashboardWidget title={$i18n.t('Quick Navigation')} class="lg:col-span-2" bodyClass="pt-3">
	<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
		{#each links as link (link.href)}
			<a
				href={resolve(link.href as unknown as '/')}
				class="group flex items-center gap-3 rounded-lg border border-border p-3 transition hover:border-primary/50 hover:bg-muted/40"
			>
				<div
					class="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground transition group-hover:text-primary"
				>
					{#if link.icon === 'users'}
						<UsersSolid className="size-4" />
					{:else if link.icon === 'eval'}
						<ChartBar className="size-4" />
					{:else if link.icon === 'wrench'}
						<Wrench className="size-4" />
					{:else if link.icon === 'cog'}
						<Cog6 className="size-4" />
					{:else if link.icon === 'shield'}
						<Shield className="size-4" />
					{:else}
						<BookOpen className="size-4" />
					{/if}
				</div>
				<div class="min-w-0 flex-1">
					<div class="text-sm font-medium text-foreground">{$i18n.t(link.label)}</div>
					<div class="truncate text-xs text-muted-foreground">{$i18n.t(link.desc)}</div>
				</div>
				<ChevronRight
					className="size-4 shrink-0 text-muted-foreground transition group-hover:text-primary"
				/>
			</a>
		{/each}
	</div>
</DashboardWidget>
