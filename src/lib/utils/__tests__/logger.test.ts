import { describe, it, expect, beforeEach } from 'vitest';
import { logger } from '../logger';
import type { LogEntry, LogTransport } from '../logger';

function createMockTransport(): LogTransport & { entries: LogEntry[] } {
	const entries: LogEntry[] = [];
	return {
		entries,
		log(entry: LogEntry): void {
			entries.push(entry);
		}
	};
}

describe('logger', () => {
	let transport: ReturnType<typeof createMockTransport>;

	beforeEach(() => {
		// Create a fresh logger for each test by importing a new instance is not
		// possible with module-singleton, so we add a fresh transport each time
		// and rely on it to capture entries.
		transport = createMockTransport();
		logger.addTransport(transport);
	});

	it('logger.error() outputs structured entry with correct level', () => {
		const err = new Error('boom');
		logger.error('test-ctx', 'something failed', err, { key: 'value' });

		const entry = transport.entries.find((e) => e.level === 'error' && e.context === 'test-ctx');
		expect(entry).toBeDefined();
		expect(entry!.level).toBe('error');
		expect(entry!.context).toBe('test-ctx');
		expect(entry!.message).toBe('something failed');
		expect(entry!.error).toBe(err);
		expect(entry!.data).toEqual({ key: 'value' });
		expect(entry!.timestamp).toBeTruthy();
	});

	it('logger.warn() outputs with warn level', () => {
		logger.warn('warn-ctx', 'caution ahead', { detail: 42 });

		const entry = transport.entries.find((e) => e.level === 'warn' && e.context === 'warn-ctx');
		expect(entry).toBeDefined();
		expect(entry!.level).toBe('warn');
		expect(entry!.message).toBe('caution ahead');
		expect(entry!.data).toEqual({ detail: 42 });
	});

	it('logger.info() outputs with info level', () => {
		logger.info('info-ctx', 'all good');

		const entry = transport.entries.find((e) => e.level === 'info' && e.context === 'info-ctx');
		expect(entry).toBeDefined();
		expect(entry!.level).toBe('info');
		expect(entry!.message).toBe('all good');
	});

	it('logger.debug() outputs with debug level', () => {
		// Default min level is 'info', so debug won't be emitted unless we lower it.
		// Create a dedicated transport + set level
		const debugTransport = createMockTransport();
		logger.addTransport(debugTransport);
		logger.setLevel('debug');

		logger.debug('dbg-ctx', 'trace info', { x: 1 });

		const entry = debugTransport.entries.find(
			(e) => e.level === 'debug' && e.context === 'dbg-ctx'
		);
		expect(entry).toBeDefined();
		expect(entry!.level).toBe('debug');
		expect(entry!.message).toBe('trace info');
		expect(entry!.data).toEqual({ x: 1 });

		// Reset level back to default
		logger.setLevel('info');
	});

	it('custom transport receives log entries via addTransport()', () => {
		logger.info('transport-ctx', 'hello transport');

		expect(transport.entries.length).toBeGreaterThanOrEqual(1);
		const entry = transport.entries.find(
			(e) => e.context === 'transport-ctx' && e.message === 'hello transport'
		);
		expect(entry).toBeDefined();
	});

	it('level filtering works: set level to warn, info does not call transport', () => {
		const filteredTransport = createMockTransport();
		logger.addTransport(filteredTransport);
		logger.setLevel('warn');

		logger.info('filtered-ctx', 'should be filtered');
		logger.warn('warn-pass-ctx', 'should pass');

		const infoEntry = filteredTransport.entries.find(
			(e) => e.level === 'info' && e.context === 'filtered-ctx'
		);
		const warnEntry = filteredTransport.entries.find(
			(e) => e.level === 'warn' && e.context === 'warn-pass-ctx'
		);

		expect(infoEntry).toBeUndefined();
		expect(warnEntry).toBeDefined();

		// Reset level back to default
		logger.setLevel('info');
	});
});
