import { EventSourceParserStream } from 'eventsource-parser/stream';
import type { EventSourceMessage } from 'eventsource-parser/stream';
import { logger } from '$lib/utils/logger';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type TextStreamUpdate = {
	done: boolean;
	value: string;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	sources?: any;
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	selectedModelId?: any;
	error?: unknown;
	usage?: ResponseUsage;
};

type ResponseUsage = {
	prompt_tokens: number;
	completion_tokens: number;
	total_tokens: number;
	[other: string]: unknown;
};

// ---------------------------------------------------------------------------
// Stream processing
// ---------------------------------------------------------------------------

export async function createOpenAITextStream(
	responseBody: ReadableStream<Uint8Array>,
	splitLargeDeltas: boolean
): Promise<AsyncGenerator<TextStreamUpdate>> {
	const eventStream = responseBody
		.pipeThrough(new TextDecoderStream())
		.pipeThrough(new EventSourceParserStream())
		.getReader();
	let iterator = openAIStreamToIterator(eventStream);
	if (splitLargeDeltas) {
		iterator = streamLargeDeltasAsRandomChunks(iterator);
	}
	return iterator;
}

async function* openAIStreamToIterator(
	reader: ReadableStreamDefaultReader<EventSourceMessage>
): AsyncGenerator<TextStreamUpdate> {
	while (true) {
		const { value, done } = await reader.read();
		if (done) {
			yield { done: true, value: '' };
			break;
		}
		if (!value) {
			continue;
		}
		const data = value.data;
		if (data.startsWith('[DONE]')) {
			yield { done: true, value: '' };
			break;
		}

		try {
			const parsedData = JSON.parse(data);

			if (parsedData.error) {
				yield { done: true, value: '', error: parsedData.error };
				break;
			}

			if (parsedData.sources) {
				yield { done: false, value: '', sources: parsedData.sources };
				continue;
			}

			if (parsedData.selected_model_id) {
				yield { done: false, value: '', selectedModelId: parsedData.selected_model_id };
				continue;
			}

			if (parsedData.usage) {
				yield { done: false, value: '', usage: parsedData.usage };
				continue;
			}

			yield {
				done: false,
				value: parsedData.choices?.[0]?.delta?.content ?? ''
			};
		} catch (e) {
			logger.error('streaming', 'Error extracting delta from SSE event:', e instanceof Error ? e : undefined, e);
		}
	}
}

async function* streamLargeDeltasAsRandomChunks(
	iterator: AsyncGenerator<TextStreamUpdate>
): AsyncGenerator<TextStreamUpdate> {
	for await (const textStreamUpdate of iterator) {
		if (textStreamUpdate.done) {
			yield textStreamUpdate;
			return;
		}

		if (textStreamUpdate.error) {
			yield textStreamUpdate;
			continue;
		}
		if (textStreamUpdate.sources) {
			yield textStreamUpdate;
			continue;
		}
		if (textStreamUpdate.selectedModelId) {
			yield textStreamUpdate;
			continue;
		}
		if (textStreamUpdate.usage) {
			yield textStreamUpdate;
			continue;
		}

		let content = textStreamUpdate.value;
		if (content.length < 5) {
			yield { done: false, value: content };
			continue;
		}
		while (content != '') {
			const chunkSize = Math.min(Math.floor(Math.random() * 3) + 1, content.length);
			const chunk = content.slice(0, chunkSize);
			yield { done: false, value: chunk };
			if (document?.visibilityState !== 'hidden') {
				await sleep(5);
			}
			content = content.slice(chunkSize);
		}
	}
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
