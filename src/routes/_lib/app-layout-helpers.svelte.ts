/*
 * SPDX-FileCopyrightText: 2026 BC Card
 * SPDX-License-Identifier: Apache-2.0
 */

import { isLastActiveTab, mobile } from '$lib/stores';

const BREAKPOINT = 768;

export function createActiveTabSync(broadcastChannel: BroadcastChannel) {
	const handleMessage = (event: MessageEvent) => {
		if (event.data === 'active') {
			isLastActiveTab.set(false);
		}
	};

	const handleVisibilityChange = () => {
		if (document.visibilityState === 'visible') {
			isLastActiveTab.set(true);
			broadcastChannel.postMessage('active');
		}
	};

	broadcastChannel.onmessage = handleMessage;
	document.addEventListener('visibilitychange', handleVisibilityChange);
	handleVisibilityChange();

	return () => {
		document.removeEventListener('visibilitychange', handleVisibilityChange);
	};
}

export function createResponsiveHandler() {
	const onResize = () => {
		mobile.set(window.innerWidth < BREAKPOINT);
	};

	mobile.set(window.innerWidth < BREAKPOINT);
	window.addEventListener('resize', onResize);

	return () => {
		window.removeEventListener('resize', onResize);
	};
}
