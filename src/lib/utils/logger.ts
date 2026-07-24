/**
 * Structured logging utility for BCGPT WebUI.
 *
 * Provides leveled logging (debug, info, warn, error) with an extensible
 * transport system. The default ConsoleTransport outputs human-readable
 * messages; additional transports (e.g. Sentry, remote) can be added via
 * `logger.addTransport()`.
 *
 * Usage:
 *   import { logger } from '$lib/utils/logger';
 *   logger.error('auth', 'Failed to fetch admin details', err);
 *   logger.info('chat', 'Chat created', { chatId: 'abc' });
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
	timestamp: string;
	level: LogLevel;
	context: string;
	message: string;
	data?: unknown;
	error?: Error;
}

interface LogTransport {
	log(entry: LogEntry): void;
}

const LOG_LEVEL_SEVERITY: Record<LogLevel, number> = {
	debug: 0,
	info: 1,
	warn: 2,
	error: 3
};

/**
 * Default transport — outputs human-readable messages to the browser console.
 * Uses the appropriate console method for each log level.
 */
class ConsoleTransport implements LogTransport {
	public log(entry: LogEntry): void {
		const { timestamp, level, context, message, data, error } = entry;
		const prefix = `[${level.toUpperCase()}] [${timestamp}] [${context}]`;

		switch (level) {
			case 'error':
				if (error) {
					console.error(prefix, message, error, data ?? '');
				} else {
					console.error(prefix, message, data ?? '');
				}
				break;
			case 'warn':
				console.warn(prefix, message, data ?? '');
				break;
			case 'info':
				console.info(prefix, message, data ?? '');
				break;
			case 'debug':
				console.debug(prefix, message, data ?? '');
				break;
		}
	}
}

class Logger {
	private transports: LogTransport[];
	private minLevel: LogLevel;

	constructor(transports: LogTransport[] = [], minLevel: LogLevel = 'info') {
		this.transports = transports.length > 0 ? transports : [new ConsoleTransport()];
		this.minLevel = minLevel;
	}

	public addTransport(transport: LogTransport): void {
		this.transports.push(transport);
	}

	public setLevel(level: LogLevel): void {
		this.minLevel = level;
	}

	public error(context: string, message: string, error?: Error, data?: unknown): void {
		this.write('error', context, message, data, error);
	}

	public warn(context: string, message: string, data?: unknown): void {
		this.write('warn', context, message, data);
	}

	public info(context: string, message: string, data?: unknown): void {
		this.write('info', context, message, data);
	}

	public debug(context: string, message: string, data?: unknown): void {
		this.write('debug', context, message, data);
	}

	private write(
		level: LogLevel,
		context: string,
		message: string,
		data?: unknown,
		error?: Error
	): void {
		if (LOG_LEVEL_SEVERITY[level] < LOG_LEVEL_SEVERITY[this.minLevel]) {
			return;
		}

		const entry: LogEntry = {
			timestamp: new Date().toISOString(),
			level,
			context,
			message
		};

		if (data !== undefined) {
			entry.data = data;
		}

		if (error !== undefined) {
			entry.error = error;
		}

		for (const transport of this.transports) {
			transport.log(entry);
		}
	}
}

const logger = new Logger();

export { logger };
export type { LogEntry, LogTransport, LogLevel };
