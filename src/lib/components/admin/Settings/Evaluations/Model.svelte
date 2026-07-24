<script lang="ts">
	/**
	 * Arena Model Card
	 *
	 * Displays a single arena model entry with name, description, and profile image.
	 * Provides a gear button to open the edit modal (ArenaModelModal).
	 */
	import Cog6 from '$lib/components/icons/Cog6.svelte';
	import { Button } from '$lib/components/ui/button';
	import ArenaModelModal from './ArenaModelModal.svelte';

	interface Props {
		/** The arena model data object */
		model: Record<string, unknown>;
		/** Called when the model is edited and saved */
		onEdit?: (e: CustomEvent) => void;
		/** Called when the model is deleted */
		onDelete?: (e: CustomEvent) => void;
	}

	let { model, onEdit = () => {}, onDelete = () => {} }: Props = $props();

	/** Whether the edit modal is showing */
	let showModel = $state(false);
</script>

<ArenaModelModal
	bind:show={showModel}
	edit={true}
	{model}
	onSubmit={async (e: CustomEvent) => {
		onEdit?.(e.detail);
	}}
	onDelete={async () => {
		onDelete?.();
	}}
/>

<div class="py-0.5">
	<div class="flex justify-between items-center mb-1">
		<div class="flex flex-col flex-1">
			<div class="flex gap-2.5 items-center">
				<img
					src={model.meta.profile_image_url}
					alt={model.name}
					class="size-8 rounded-full object-cover shrink-0"
				/>

				<div class="w-full flex flex-col">
					<div class="flex items-center gap-1">
						<div class="shrink-0 line-clamp-1">
							{model.name}
						</div>
					</div>

					<div class="flex items-center gap-1">
						<div class=" text-xs w-full text-muted-foreground bg-transparent line-clamp-1">
							{model?.meta?.description ?? model.id}
						</div>
					</div>
				</div>
			</div>
		</div>

		<div class="flex items-center">
			<Button
				variant="ghost"
				size="icon"
				type="button"
				onclick={() => {
					showModel = true;
				}}
			>
				<Cog6 />
			</Button>
		</div>
	</div>
</div>
