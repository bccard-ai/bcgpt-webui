<script lang="ts">
	import { toast } from 'svelte-sonner';

	import { getContext, tick } from 'svelte';
	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	import { chatCompletion } from '$lib/apis/openai';

	import ChatBubble from '$lib/components/icons/ChatBubble.svelte';
	import LightBlub from '$lib/components/icons/LightBlub.svelte';
	import Markdown from '../Messages/Markdown.svelte';
	import Skeleton from '../Messages/Skeleton.svelte';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	interface Props {
		/** Unique identifier for this floating buttons instance */
		id?: string;
		/** The model to use for AI-powered explanations */
		model?: string | null;
		/** Conversation history context for the AI request */
		messages?: Array<{ role: string; content: string }>;
		/** Callback to add the Q&A pair to the chat history */
		onAdd?: (payload: {
			modelId: string | null;
			parentId: string;
			messages: Array<{ role: string; content: string }>;
		}) => void;
	}

	let { id = '', model = null, messages = [], onAdd = () => {} }: Props = $props();

	/** Whether the text input is visible */
	let floatingInput = $state(false);

	/** Text selected by the user that triggered the floating buttons */
	let selectedText = $state('');

	/** Current value of the floating text input */
	let floatingInputValue = $state('');

	/** The prompt sent to the AI */
	let prompt = $state('');

	/** Streaming response content from the AI */
	let responseContent = $state<string | null>(null);

	/** Whether the AI response is complete */
	let responseDone = $state(false);

	/**
	 * Auto-scroll the response container if the user is near the bottom.
	 * Uses a 50px buffer to avoid fighting with manual scroll position.
	 */
	const autoScroll = (): void => {
		const container = document.getElementById('response-container');
		if (!container) return;
		if (container.scrollHeight - container.clientHeight <= container.scrollTop + 50) {
			container.scrollTop = container.scrollHeight;
		}
	};

	/**
	 * Stream a chat completion response from the API.
	 * Handles SSE parsing, content accumulation, and auto-scrolling.
	 * Returns true on success, false on error.
	 */
	const streamChatCompletion = async (
		requestMessages: Array<{ role: string; content: string }>
	): Promise<boolean> => {
		responseContent = '';
		const [res] = await chatCompletion('', {
			model: model!,
			messages: requestMessages.map((m) => ({ role: m.role, content: m.content })),
			stream: true
		});

		if (!res?.ok) {
			toast.error($i18n.t('An error occurred while fetching the explanation'));
			return false;
		}

		const reader = res.body!.getReader();
		const decoder = new TextDecoder();

		while (true) {
			const { done, value } = await reader.read();
			if (done) break;

			const chunk = decoder.decode(value, { stream: true });
			const lines = chunk.split('\n').filter((line) => line.trim() !== '');

			for (const line of lines) {
				if (!line.startsWith('data: ')) continue;

				if (line.startsWith('data: [DONE]')) {
					responseDone = true;
					await tick();
					autoScroll();
					continue;
				}

				try {
					const data = JSON.parse(line.slice(6));
					if (data.choices?.[0]?.delta?.content) {
						responseContent += data.choices[0].delta.content;
						autoScroll();
					}
				} catch {
					// Ignore malformed SSE chunks
				}
			}
		}

		return true;
	};

	/** Handle the "Ask" action: user types a question about selected text */
	const askHandler = async (): Promise<void> => {
		if (!model) {
			toast.error($i18n.t('Model not selected'));
			return;
		}
		prompt = `${floatingInputValue}\n\`\`\`\n${selectedText}\n\`\`\``;
		floatingInputValue = '';

		await streamChatCompletion([...messages, { role: 'user', content: prompt }]);
	};

	/** Handle the "Explain" action: ask the AI to explain the selected text */
	const explainHandler = async (): Promise<void> => {
		if (!model) {
			toast.error($i18n.t('Model not selected'));
			return;
		}
		selectedText = window.getSelection().toString();
		const explainText = $i18n.t('Explain this section to me in more detail');
		prompt = `${explainText}\n\n\`\`\`\n${selectedText}\n\`\`\``;

		await streamChatCompletion([...messages, { role: 'user', content: prompt }]);
	};

	/** Add the current Q&A pair to the chat history */
	const addHandler = (): void => {
		onAdd({
			modelId: model,
			parentId: id,
			messages: [
				{ role: 'user', content: prompt },
				{ role: 'assistant', content: responseContent ?? '' }
			]
		});
	};

	/** Reset all floating button state */
	export const closeHandler = (): void => {
		responseContent = null;
		responseDone = false;
		floatingInput = false;
		floatingInputValue = '';
	};
</script>

<div
	id={`floating-buttons-${id}`}
	class="absolute rounded-lg mt-1 text-xs z-9999"
	style="display: none"
>
	{#if responseContent === null}
		{#if !floatingInput}
			<div
				class="flex flex-row gap-0.5 shrink-0 p-1 bg-white dark:bg-gray-850 dark:text-gray-100 text-medium rounded-lg shadow-xl"
			>
				<button
					class="px-1 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-sm flex items-center gap-1 min-w-fit"
					onclick={async () => {
						selectedText = window.getSelection().toString();
						floatingInput = true;

						await tick();
						setTimeout(() => {
							document.getElementById('floating-message-input')?.focus();
						}, 0);
					}}
				>
					<ChatBubble className="size-3 shrink-0" />
					<div class="shrink-0">{$i18n.t('Ask')}</div>
				</button>
				<button
					class="px-1 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-sm flex items-center gap-1 min-w-fit"
					onclick={() => {
						selectedText = window.getSelection().toString();
						explainHandler();
					}}
				>
					<LightBlub className="size-3 shrink-0" />
					<div class="shrink-0">{$i18n.t('Explain')}</div>
				</button>
			</div>
		{:else}
			<div
				class="py-1 flex dark:text-gray-100 bg-gray-50 dark:bg-gray-800 border border-gray-100 dark:border-gray-850 w-72 rounded-full shadow-xl"
			>
				<input
					type="text"
					id="floating-message-input"
					class="ml-5 bg-transparent outline-hidden w-full flex-1 text-sm"
					placeholder={$i18n.t('Ask a question')}
					bind:value={floatingInputValue}
					onkeydown={(e: KeyboardEvent) => {
						if (e.key === 'Enter') {
							askHandler();
						}
					}}
				/>

				<div class="ml-1 mr-2">
					<button
						class="{floatingInputValue !== ''
							? 'bg-black text-white hover:bg-gray-900 dark:bg-white dark:text-black dark:hover:bg-gray-100 '
							: 'text-white bg-gray-200 dark:text-gray-900 dark:bg-gray-700 disabled'} transition rounded-full p-1.5 m-0.5 self-center"
						aria-label={$i18n.t('Send')}
						onclick={askHandler}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="size-4"
						>
							<path
								fill-rule="evenodd"
								d="M8 14a.75.75 0 0 1-.75-.75V4.56L4.03 7.78a.75.75 0 0 1-1.06-1.06l4.5-4.5a.75.75 0 0 1 1.06 0l4.5 4.5a.75.75 0 0 1-1.06 1.06L8.75 4.56v8.69A.75.75 0 0 1 8 14Z"
								clip-rule="evenodd"
							/>
						</svg>
					</button>
				</div>
			</div>
		{/if}
	{:else}
		<div class="bg-white dark:bg-gray-850 dark:text-gray-100 rounded-xl shadow-xl w-80 max-w-full">
			<div
				class="bg-gray-50/50 dark:bg-gray-800 dark:text-gray-100 text-medium rounded-xl px-3.5 py-3 w-full"
			>
				<div class="font-medium">
					<Markdown id={`${id}-float-prompt`} content={prompt} />
				</div>
			</div>

			<div
				class="bg-white dark:bg-gray-850 dark:text-gray-100 text-medium rounded-xl px-3.5 py-3 w-full"
			>
				<div class=" max-h-80 overflow-y-auto w-full markdown-prose-xs" id="response-container">
					{#if responseContent.trim() === ''}
						<Skeleton size="sm" />
					{:else}
						<Markdown id={`${id}-float-response`} content={responseContent} />
					{/if}

					{#if responseDone}
						<div class="flex justify-end pt-3 text-sm font-medium">
							<button
								class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
								onclick={addHandler}
							>
								{$i18n.t('Add')}
							</button>
						</div>
					{/if}
				</div>
			</div>
		</div>
	{/if}
</div>
