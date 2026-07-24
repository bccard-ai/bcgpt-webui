<script lang="ts">
	import { getContext } from 'svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	import { DropdownMenu } from 'bits-ui';
	import { activeUserIds } from '$lib/stores';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface PreviewUser {
		id: string;
		name?: string;
		profile_image_url?: string;
	}

	/**
	 * A dropdown profile preview that shows a user's avatar, name,
	 * and active/away status when hovering over a profile image.
	 *
	 * @example
	 * ```svelte
	 * <ProfilePreview user={{ id: '123', name: 'Alice' }}>
	 *   <img src="avatar.png" alt="avatar" />
	 * </ProfilePreview>
	 * ```
	 *
	 * @param side - The side of the anchor to render the dropdown on.
	 * @param align - The alignment of the dropdown relative to the anchor.
	 * @param user - The user object to preview.
	 * @param children - Snippet for the trigger element.
	 * @param content - Optional custom snippet for the dropdown content.
	 * @param onchange - Callback when the dropdown open state changes.
	 */
	interface Props {
		side?: string;
		align?: string;
		user?: PreviewUser | null;
		children?: import('svelte').Snippet;
		content?: import('svelte').Snippet;

		onchange?: (...args: unknown[]) => void;
	}

	let {
		side = 'right',
		align = 'top',
		user = null,
		children,
		content,
		onchange = () => {}
	}: Props = $props();
	let show = $state(false);
</script>

<DropdownMenu.Root
	bind:open={show}
	closeFocus={false}
	onOpenChange={(state) => {
		onchange?.(state);
	}}
	typeahead={false}
>
	<DropdownMenu.Trigger>
		{@render children?.()}
	</DropdownMenu.Trigger>

	{#if content}{@render content()}{:else}
		<DropdownMenu.Portal>
			<DropdownMenu.Content
				class="max-w-full w-[240px] rounded-lg z-9999 bg-white dark:bg-black dark:text-white shadow-lg"
				sideOffset={8}
				{side}
				{align}
			>
				{#if user}
					<div class=" flex flex-col gap-2 w-full rounded-lg">
						<div class="py-8 relative bg-gray-900 rounded-t-lg">
							<img
								crossorigin="anonymous"
								src={user?.profile_image_url ?? `/static/favicon.png`}
								class=" absolute -bottom-5 left-3 size-12 ml-0.5 object-cover rounded-full -translate-y-[1px]"
								alt="profile"
							/>
						</div>

						<div class=" flex flex-col pt-4 pb-2.5 px-4">
							<div class=" -mb-1">
								<span class="font-medium text-sm line-clamp-1"> {user.name} </span>
							</div>

							<div class=" flex items-center gap-2">
								{#if $activeUserIds.includes(user.id)}
									<div>
										<span class="relative flex size-2">
											<span
												class="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"
											></span>
											<span class="relative inline-flex rounded-full size-2 bg-green-500"></span>
										</span>
									</div>

									<div class=" -translate-y-[1px]">
										<span class="text-xs"> {$i18n.t('Active')} </span>
									</div>
								{:else}
									<div>
										<span class="relative flex size-2">
											<span class="relative inline-flex rounded-full size-2 bg-gray-500"></span>
										</span>
									</div>

									<div class=" -translate-y-[1px]">
										<span class="text-xs"> {$i18n.t('Away')} </span>
									</div>
								{/if}
							</div>
						</div>
					</div>
				{/if}
			</DropdownMenu.Content>
		</DropdownMenu.Portal>
	{/if}
</DropdownMenu.Root>
