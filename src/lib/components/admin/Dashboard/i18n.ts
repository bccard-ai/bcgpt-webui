import { getContext } from 'svelte';
import type { i18n as i18nType } from 'i18next';
import type { Writable } from 'svelte/store';

/** Shared accessor for the i18n store set on the app context. */
export function useI18n(): Writable<i18nType> {
	return getContext<Writable<i18nType>>('i18n');
}
