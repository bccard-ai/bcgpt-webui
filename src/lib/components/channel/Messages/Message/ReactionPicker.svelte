<script lang="ts">
	import { getContext } from 'svelte';
	import { DropdownMenu } from 'bits-ui';
	import emojiGroups from '$lib/emoji-groups.json';
	import emojiShortCodes from '$lib/emoji-shortcodes.json';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	// @ts-expect-error - @sveltejs/svelte-virtual-list ships no type declarations
	import VirtualList from '@sveltejs/svelte-virtual-list';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	interface EmojiItem {
		type: 'emoji';
		name: string;
		shortCodes: string[];
	}

	interface GroupItem {
		type: 'group';
		label: string;
	}

	type EmojiRow = (EmojiItem | GroupItem)[];

	/**
	 * A dropdown reaction picker with search and virtualized scrolling.
	 * Allows users to browse and select emoji reactions by group or search term.
	 *
	 * @example
	 * ```svelte
	 * <ReactionPicker
	 *   onClose={() => {}}
	 *   onSubmit={(name) => addReaction(name)}
	 * >
	 *   <button>😀</button>
	 * </ReactionPicker>
	 * ```
	 *
	 * @param onClose - Callback when the picker is closed.
	 * @param onSubmit - Callback with the selected emoji short code name.
	 * @param side - The side of the anchor to render the dropdown on.
	 * @param align - The alignment of the dropdown relative to the anchor.
	 * @param user - Optional user context (unused internally).
	 * @param children - Snippet for the trigger element.
	 */
	interface Props {
		onClose?: () => void;
		onSubmit?: (name: string) => void;
		side?: string;
		align?: string;
		user?: unknown;
		children?: import('svelte').Snippet;
	}

	let {
		onClose = () => {},
		onSubmit = (_name: string) => {},
		side = 'top',
		align = 'start',
		user: _user = null,
		children
	}: Props = $props();

	let show = $state(false);
	let search = $state('');

	let emojis = $derived(() => {
		if (search) {
			return Object.keys(emojiShortCodes).reduce<Record<string, unknown>>((acc, key) => {
				if (key.includes(search)) {
					acc[key] = emojiShortCodes[key];
				} else {
					const value = emojiShortCodes[key];
					if (Array.isArray(value)) {
						const filtered = value.filter((emoji: string) => emoji.includes(search));
						if (filtered.length) {
							acc[key] = filtered;
						}
					} else {
						if ((value as string).includes(search)) {
							acc[key] = value;
						}
					}
				}
				return acc;
			}, {});
		} else {
			return emojiShortCodes;
		}
	});

	let emojiRows = $derived(() => {
		const currentEmojis = emojis();
		const flat: (EmojiItem | GroupItem)[] = [];
		Object.keys(emojiGroups).forEach((group) => {
			const groupEmojis = emojiGroups[group].filter((emoji: string) => currentEmojis[emoji]);
			if (groupEmojis.length > 0) {
				flat.push({ type: 'group', label: group });
				flat.push(
					...groupEmojis.map((emoji: string) => ({
						type: 'emoji' as const,
						name: emoji,
						shortCodes:
							typeof emojiShortCodes[emoji] === 'string'
								? [emojiShortCodes[emoji]]
								: emojiShortCodes[emoji]
					}))
				);
			}
		});

		const rows: EmojiRow[] = [];
		let currentRow: (EmojiItem | GroupItem)[] = [];
		flat.forEach((item) => {
			if (item.type === 'emoji') {
				currentRow.push(item);
				if (currentRow.length === 8) {
					rows.push(currentRow);
					currentRow = [];
				}
			} else if (item.type === 'group') {
				if (currentRow.length > 0) {
					rows.push(currentRow);
					currentRow = [];
				}
				rows.push([item]);
			}
		});
		if (currentRow.length > 0) {
			rows.push(currentRow);
		}
		return rows;
	});

	const ROW_HEIGHT = 48;

	function selectEmoji(emoji: EmojiItem) {
		const selectedCode = emoji.shortCodes[0];
		onSubmit(selectedCode);
		show = false;
	}
</script>

<DropdownMenu.Root
	bind:open={show}
	closeFocus={false}
	onOpenChange={(state) => {
		if (!state) {
			search = '';
			onClose();
		}
	}}
	typeahead={false}
>
	<DropdownMenu.Trigger>
		{@render children?.()}
	</DropdownMenu.Trigger>
	<DropdownMenu.Portal>
		<DropdownMenu.Content
			class="max-w-full w-80 bg-gray-50 dark:bg-gray-850 rounded-lg z-9999 shadow-lg dark:text-white"
			sideOffset={8}
			{side}
			{align}
		>
			<div class="mb-1 px-3 pt-2 pb-2">
				<input
					type="text"
					class="w-full text-sm bg-transparent outline-hidden"
					placeholder={$i18n.t('Search all emojis')}
					bind:value={search}
				/>
			</div>
			<div class="w-full flex justify-start h-96 overflow-y-auto px-3 pb-3 text-sm">
				{#if emojiRows().length === 0}
					<div class="text-center text-xs text-gray-500 dark:text-gray-400">
						{$i18n.t('No results')}
					</div>
				{:else}
					<div class="w-full flex ml-0.5">
						<VirtualList rowHeight={ROW_HEIGHT} items={emojiRows()} height={384}>
							{#snippet children({ item })}
								<div class="w-full">
									{#if item.length === 1 && item[0].type === 'group'}
										<div class="text-xs font-medium mb-2 text-gray-500 dark:text-gray-400">
											{item[0].label}
										</div>
									{:else}
										<div class="flex items-center gap-1.5 w-full">
											{#each item as emojiItem (emojiItem.name)}
												<Tooltip
													content={emojiItem.shortCodes.map((code) => `:${code}:`).join(', ')}
													placement="top"
												>
													<button
														class="p-1.5 rounded-lg cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700 transition"
														onclick={() => selectEmoji(emojiItem)}
													>
														<img
															src="/assets/emojis/{emojiItem.name.toLowerCase()}.svg"
															alt={emojiItem.name}
															class="size-5"
															loading="lazy"
														/>
													</button>
												</Tooltip>
											{/each}
										</div>
									{/if}
								</div>
							{/snippet}
						</VirtualList>
					</div>
				{/if}
			</div>
		</DropdownMenu.Content>
	</DropdownMenu.Portal>
</DropdownMenu.Root>
