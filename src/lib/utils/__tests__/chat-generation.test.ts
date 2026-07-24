import { describe, expect, it } from 'vitest';
import {
	isChatGenerationStopSettled,
	sameChatGenerationAuthority,
	type ChatGenerationAuthority
} from '../chat-generation';

function authority(overrides: Partial<ChatGenerationAuthority> = {}): ChatGenerationAuthority {
	return {
		taskId: 'task-a',
		generationId: 'generation-a',
		chatId: 'chat-a',
		messageId: 'message-a',
		epoch: 1,
		durable: true,
		...overrides
	};
}

describe('chat generation authority', () => {
	it('accepts only the exact durable generation, chat, message, and epoch', () => {
		const captured = authority();
		expect(sameChatGenerationAuthority(captured, authority())).toBe(true);
		// The task ID is a process-local delivery locator and may be bound after
		// durable admission without changing the generation authority.
		expect(sameChatGenerationAuthority(captured, authority({ taskId: 'task-b' }))).toBe(true);
		expect(sameChatGenerationAuthority(captured, authority({ messageId: 'message-b' }))).toBe(
			false
		);
		expect(sameChatGenerationAuthority(captured, authority({ epoch: 2 }))).toBe(false);
		expect(sameChatGenerationAuthority(captured, undefined)).toBe(false);
	});

	it('prevents a delayed stop receipt from clearing a replacement generation', () => {
		const oldGeneration = authority();
		const replacement = authority({ taskId: 'task-b', generationId: 'generation-b', epoch: 2 });

		expect(sameChatGenerationAuthority(oldGeneration, replacement)).toBe(false);
	});

	it('settles terminal and mismatched receipts but retains nonterminal stop acceptance', () => {
		expect(
			isChatGenerationStopSettled({
				status: 'observed',
				accepted: true,
				terminal: true,
				stopped: true
			})
		).toBe(true);
		expect(
			isChatGenerationStopSettled({
				status: 'accepted',
				accepted: true,
				terminal: false,
				stopped: false
			})
		).toBe(false);
		expect(
			isChatGenerationStopSettled({
				status: 'different_generation',
				accepted: false,
				terminal: false,
				stopped: false
			})
		).toBe(true);
		expect(
			isChatGenerationStopSettled({
				status: 'unconfirmed',
				accepted: false,
				terminal: false,
				stopped: false
			})
		).toBe(false);
	});
});
