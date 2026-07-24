<script lang="ts">
	import { type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { getContext } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import Marquee from './common/Marquee.svelte';
	import SlideShow from './common/SlideShow.svelte';
	import ArrowRightCircle from './icons/ArrowRightCircle.svelte';

	/**
	 * Full-screen onboarding component shown to first-time users.
	 * Features a slideshow background, marquee tagline, and a "Get Started" button.
	 *
	 * @example
	 * ```svelte
	 * <OnBoarding
	 *   show={isFirstTime}
	 *   getStartedHandler={() => completeOnboarding()}
	 * />
	 * ```
	 *
	 * @param show - Whether to show the onboarding screen.
	 * @param getStartedHandler - Callback invoked when the user clicks "Get started".
	 */
	interface Props {
		show?: boolean;
		getStartedHandler?: () => void;
	}

	let { show = true, getStartedHandler = () => {} }: Props = $props();

	function setLogoImage() {
		const logo = document.getElementById('logo') as HTMLImageElement | null;

		if (logo) {
			const isDarkMode = document.documentElement.classList.contains('dark');

			if (isDarkMode) {
				const darkImage = new Image();
				darkImage.src = '/static/favicon-dark.png';

				darkImage.onload = () => {
					logo.src = '/static/favicon-dark.png';
					logo.style.filter = '';
				};

				darkImage.onerror = () => {
					logo.style.filter = 'invert(1)';
				};
			}
		}
	}

	$effect(() => {
		if (show) {
			setLogoImage();
		}
	});
</script>

{#if show}
	<div class="w-full h-screen max-h-[100dvh] text-white relative">
		<div class="fixed m-10 z-50">
			<div class="flex space-x-2">
				<div class=" self-center">
					<img
						id="logo"
						crossorigin="anonymous"
						src="/static/favicon.png"
						class="w-16 rounded-full"
						alt="logo"
					/>
				</div>
			</div>
		</div>

		<SlideShow duration={5000} />

		<div
			class="w-full h-full absolute top-0 left-0 bg-linear-to-t from-20% from-black to-transparent"
		></div>

		<div class="w-full h-full absolute top-0 left-0 backdrop-blur-xs bg-black/50"></div>

		<div class="relative bg-transparent w-full min-h-screen flex z-10">
			<div class="flex flex-col justify-end w-full items-center pb-10 text-center">
				<div class="text-5xl lg:text-7xl font-secondary">
					<Marquee
						duration={5000}
						words={[
							$i18n.t('Navigate the sea of wisdom'),
							$i18n.t('Open up a new world'),
							$i18n.t('Discover infinite possibilities'),
							$i18n.t('Immerse yourself in deep knowledge'),
							$i18n.t('Encounter a world of wonder'),
							$i18n.t('Ignite the spark of curiosity'),
							$i18n.t('Forge a new path'),
							$i18n.t('Uncover hidden secrets'),
							$i18n.t('Follow the compass of wisdom'),
							$i18n.t('Begin a journey of the mind')
						]}
					/>

					<div class="mt-0.5">{$i18n.t(`Always with you, everywhere`)}</div>
				</div>

				<div class="flex justify-center mt-8">
					<div class="flex flex-col justify-center items-center">
						<button
							class="relative z-20 flex p-1 rounded-full bg-white/5 hover:bg-white/10 transition font-medium text-sm"
							onclick={() => {
								getStartedHandler();
							}}
						>
							<ArrowRightCircle className="size-6" />
						</button>
						<div class="mt-1.5 font-primary text-base font-medium">{$i18n.t(`Get started`)}</div>
					</div>
				</div>
			</div>
		</div>
	</div>
{/if}
