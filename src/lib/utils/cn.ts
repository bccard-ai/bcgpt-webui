import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge conditional class names and de-duplicate conflicting Tailwind utilities.
 *
 * Used by the shadcn-svelte-style primitives under `$lib/components/ui/*`. Kept
 * in its own module (`$lib/utils/cn`) so it never collides with the legacy
 * `$lib/utils` barrel (`src/lib/utils/index.ts`) — both hand-placed components
 * (`import { cn } from "$lib/utils/cn"`) and CLI-generated ones
 * (`from "$lib/utils/cn.js"`) resolve here via Vite's extension resolution.
 */
export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}
