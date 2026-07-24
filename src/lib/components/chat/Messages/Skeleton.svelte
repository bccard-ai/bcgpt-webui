<script lang="ts">
	/** Supported skeleton sizes */
	type SkeletonSize = 'md' | 'sm';

	/** Props for the Skeleton component - displays a loading placeholder */
	interface Props {
		/** Controls the sizing variant of the skeleton rows */
		size?: SkeletonSize;
	}

	let { size = 'md' }: Props = $props();

	/** Returns the Tailwind height class for the given size */
	function heightClass(s: SkeletonSize): string {
		return s === 'md' ? 'h-2' : 'h-1.5';
	}

	/** Returns the Tailwind vertical spacing class for the given size */
	function spacingClass(s: SkeletonSize): string {
		return s === 'md' ? 'space-y-2' : 'space-y-1.5';
	}
</script>

<div class="w-full mt-2 mb-2">
	<div class="animate-pulse flex w-full">
		<div class="{spacingClass(size)} w-full">
			<div class="{heightClass(size)} bg-gray-200 dark:bg-gray-600 rounded-sm mr-14"></div>

			<div class="grid grid-cols-3 gap-4">
				<div class="{heightClass(size)} bg-gray-200 dark:bg-gray-600 rounded-sm col-span-2"></div>
				<div class="{heightClass(size)} bg-gray-200 dark:bg-gray-600 rounded-sm col-span-1"></div>
			</div>
			<div class="grid grid-cols-4 gap-4">
				<div class="{heightClass(size)} bg-gray-200 dark:bg-gray-600 rounded-sm col-span-1"></div>
				<div class="{heightClass(size)} bg-gray-200 dark:bg-gray-600 rounded-sm col-span-2"></div>
				<div class="{heightClass(size)} bg-gray-200 dark:bg-gray-600 rounded-sm col-span-1 mr-4"></div>
			</div>

			<div class="{heightClass(size)} bg-gray-200 dark:bg-gray-600 rounded-sm"></div>
		</div>
	</div>
</div>
