<script lang="ts">
	import { APP_BASE_URL } from '$lib/constants';

	/** Props for the ProfileImage component - renders a user/model avatar */
	interface Props {
		/** CSS class string applied to the img element */
		className?: string;
		/** Image source URL. Falls back to favicon if empty or invalid. */
		src?: string;
	}

	let { className = 'size-8', src = '/static/favicon.png' }: Props = $props();

	/**
	 * Resolves the effective image source URL.
	 * Returns the fallback favicon for empty strings, and `/user.png` for
	 * unrecognised external URLs that aren't from known domains.
	 */
	function resolveImageSrc(url: string): string {
		if (url === '') return '/static/favicon.png';

		const isTrustedSource =
			url.startsWith(APP_BASE_URL) ||
			url.startsWith('https://www.gravatar.com/avatar/') ||
			url.startsWith('data:') ||
			url.startsWith('/');

		return isTrustedSource ? url : '/user.png';
	}
</script>

<img
	crossorigin="anonymous"
	src={resolveImageSrc(src)}
	class="{className} object-cover rounded-full -translate-y-[1px]"
	alt="profile"
	draggable="false"
/>
