<script lang="ts">
	import { APP_BASE_URL } from '$lib/constants';
	import ImagePreview from './ImagePreview.svelte';

	/**
	 * Image — clickable image that opens a full-screen preview.
	 *
	 * Automatically prefixes relative paths with APP_BASE_URL.
	 *
	 * @example
	 * ```svelte
	 * <Image src="/uploads/photo.png" alt="Photo" />
	 * ```
	 *
	 * @props src - Image source URL
	 * @props alt - Alt text
	 * @props className - CSS classes on the button wrapper
	 * @props imageClassName - CSS classes on the img element
	 */
	interface Props {
		/** Image source URL. Relative paths get APP_BASE_URL prefix. */
		src?: string;
		/** Alt text for the image. */
		alt?: string;
		/** CSS classes on the button wrapper. */
		className?: string;
		/** CSS classes on the img element. */
		imageClassName?: string;
	}

	let {
		src = '',
		alt = '',
		className = ' w-full outline-hidden focus:outline-hidden',
		imageClassName = 'rounded-lg'
	}: Props = $props();

	let _src = $derived(src.startsWith('/') ? `${APP_BASE_URL}${src}` : src);
	let showImagePreview = $state(false);
</script>

<button
	class={className}
	onclick={() => {
		showImagePreview = true;
	}}
	type="button"
>
	<img src={_src} {alt} class={imageClassName} draggable="false" data-cy="image" />
</button>

<ImagePreview bind:show={showImagePreview} src={_src} {alt} />
