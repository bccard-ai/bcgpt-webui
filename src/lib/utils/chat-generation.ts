export interface ChatGenerationAuthority {
	taskId: string | null;
	generationId: string;
	chatId: string;
	messageId: string;
	epoch: number;
	durable: boolean;
}

export interface ChatGenerationStopReceipt {
	status: string;
	accepted: boolean;
	terminal: boolean;
	stopped: boolean;
}

/** Fence delayed task and Stop responses to the exact browser generation. */
export function sameChatGenerationAuthority(
	captured: ChatGenerationAuthority,
	current: ChatGenerationAuthority | undefined
): boolean {
	return (
		current !== undefined &&
		captured.generationId === current.generationId &&
		captured.chatId === current.chatId &&
		captured.messageId === current.messageId &&
		captured.epoch === current.epoch &&
		captured.durable === current.durable
	);
}

/** A settled receipt means this exact local generation should no longer look active. */
export function isChatGenerationStopSettled(receipt: ChatGenerationStopReceipt): boolean {
	return receipt.terminal || receipt.stopped || receipt.status === 'different_generation';
}
