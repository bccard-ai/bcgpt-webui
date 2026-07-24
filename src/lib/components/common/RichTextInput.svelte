<script lang="ts">
	import { marked } from 'marked';
	import TurndownService from 'turndown';

	const turndownService = new TurndownService({
		codeBlockStyle: 'fenced',
		headingsStyle: 'atx'
	});
	turndownService.escape = (string: string) => string;

	import { onMount, onDestroy } from 'svelte';
	import { TextSelection, type EditorState, type Transaction } from '@tiptap/pm/state';
	import type { Node as ProseMirrorNode } from '@tiptap/pm/model';
	import { Editor } from '@tiptap/core';
	import { AIAutocompletion } from './RichTextInput/AutoCompletion.js';

	import CodeBlockLowlight from '@tiptap/extension-code-block-lowlight';
	import Placeholder from '@tiptap/extension-placeholder';
	import Highlight from '@tiptap/extension-highlight';
	import Typography from '@tiptap/extension-typography';
	import StarterKit from '@tiptap/starter-kit';
	import { all, createLowlight } from 'lowlight';

	import { PASTED_TEXT_CHARACTER_LIMIT } from '$lib/constants';

	const lowlight = createLowlight(all);

	/**
	 * RichTextInput — TipTap-based rich text editor with Markdown conversion.
	 *
	 * Converts between Markdown (value prop) and ProseMirror HTML internally.
	 * Supports auto-completion, template placeholder navigation, and paste handling.
	 *
	 * @example
	 * ```svelte
	 * <RichTextInput bind:value placeholder="Type here..." onchange={(e) => handleChange(e.detail.value)} />
	 * ```
	 *
	 * @props value - Bindable Markdown (or HTML if raw=true) string
	 * @props placeholder - Placeholder text
	 * @props raw - If true, value is HTML instead of Markdown
	 * @props preserveBreaks - Preserve `<br>` tags in Markdown output
	 * @props autocomplete - Enable AI auto-completion
	 * @props messageInput - Enable message-input features (Tab templates, autofocus)
	 * @props shiftEnter - Shift+Enter for line break, plain Enter for submit
	 * @props largeTextAsFile - Convert large pasted text to file attachment
	 */
	interface Props {
		oncompositionstart?: (event: CompositionEvent) => void;
		oncompositionend?: (event: CompositionEvent) => void;
		/** CSS classes on the editor container. */
		className?: string;
		/** Placeholder text shown when empty. */
		placeholder?: string;
		/** Bindable Markdown (or HTML if raw=true) content. */
		value?: string;
		/** HTML id attribute on the editor element. */
		id?: string;
		/** Treat value as raw HTML instead of Markdown. */
		raw?: boolean;
		/** Preserve `<br>` tags during Markdown conversion. */
		preserveBreaks?: boolean;
		/** Async function that returns AI completion text. */
		generateAutoCompletion?: (text: string) => Promise<string | null>;
		/** Enable AI auto-completion. */
		autocomplete?: boolean;
		/** Enable message-input features (Tab template nav, autofocus). */
		messageInput?: boolean;
		/** Shift+Enter for line break, plain Enter for submit. */
		shiftEnter?: boolean;
		/** Convert large pasted text (> PASTED_TEXT_CHARACTER_LIMIT) to file. */
		largeTextAsFile?: boolean;
		/** Called when the editor content changes. */
		onchange?: (e: { detail: { value: string } }) => void;
		/** Called when the editor gains focus. */
		onfocus?: (e: { detail: { event: Event } }) => void;
		/** Called on keyup. */
		onkeyup?: (e: { detail: { event: Event } }) => void;
		/** Called on keydown. */
		onkeydown?: (e: { detail: { event: Event } }) => void;
		/** Called on paste (for image/large text handling). */
		onpaste?: (e: { detail: { event: Event } }) => void;
	}

	let {
		oncompositionstart = (_e: CompositionEvent) => {},
		oncompositionend = (_e: CompositionEvent) => {},
		className = 'input-prose',
		placeholder = 'Type here...',
		value = $bindable(''),
		id = '',
		raw = false,
		preserveBreaks = false,
		generateAutoCompletion = async () => null,
		autocomplete = false,
		messageInput = false,
		shiftEnter = false,
		largeTextAsFile = false,
		onchange = (_e: { detail: { value: string } }) => {},
		onfocus = (_e: { detail: { event: Event } }) => {},
		onkeyup = (_e: { detail: { event: Event } }) => {},
		onkeydown = (_e: { detail: { event: Event } }) => {},
		onpaste = (_e: { detail: { event: Event } }) => {}
	}: Props = $props();

	let element: HTMLElement = $state();
	let editor: Editor | null = $state(null);
	let cleanupNativeInput: () => void = () => {};
	let _destroyed = false;

	/** Find the next {{...}} template placeholder in the document. */
	function findNextTemplate(doc: ProseMirrorNode, from = 0): { from: number; to: number } | null {
		const patterns = [{ start: '{{', end: '}}' }];
		let result: { from: number; to: number } | null = null;

		doc.nodesBetween(from, doc.content.size, (node: ProseMirrorNode, pos: number) => {
			if (result) return false;
			if (node.isText) {
				const text: string = node.text ?? '';
				let index = Math.max(0, from - pos);
				while (index < text.length) {
					for (const pattern of patterns) {
						if (text.startsWith(pattern.start, index)) {
							const endIndex = text.indexOf(pattern.end, index + pattern.start.length);
							if (endIndex !== -1) {
								result = { from: pos + index, to: pos + endIndex + pattern.end.length };
								return false;
							}
						}
					}
					index++;
				}
			}
		});

		return result;
	}

	/** Select the next template placeholder, or cursor to end. */
	function selectNextTemplate(state: EditorState, dispatch?: (tr: Transaction) => void): boolean {
		const { doc, selection } = state;
		let template = findNextTemplate(doc, selection.to);
		if (!template) {
			template = findNextTemplate(doc, 0);
		}
		if (template && dispatch) {
			dispatch(state.tr.setSelection(TextSelection.create(doc, template.from, template.to)));
			return true;
		}
		return false;
	}

	/** Set the editor content programmatically. */
	export const setContent = (content: string) => {
		editor?.commands.setContent(content);
	};

	/** Get the current text value (Markdown or HTML depending on `raw`). */
	export const getText = (): string => {
		if (!editor) return '';
		if (!raw) {
			let text = turndownService
				.turndown(
					editor
						.getHTML()
						.replace(/<p><\/p>/g, '<br/>')
						.replace(/ {2,}/g, (m) => m.replace(/ /g, '\u00a0'))
				)
				.replace(/\u00a0/g, ' ');
			if (!preserveBreaks) {
				text = text.replace(/<br\/>/g, '');
			}
			return text;
		}
		return editor.getHTML();
	};

	/** After value updates, select the next template placeholder. */
	const selectTemplate = () => {
		if (value !== '') {
			setTimeout(() => {
				if (!editor || _destroyed) return;
				try {
					const found = selectNextTemplate(editor.view.state, editor.view.dispatch);
					if (!found) {
						const { doc } = editor.view.state;
						const safePos = Math.min(doc.content.size - 1, doc.content.size);
						const resolved = doc.resolve(Math.max(0, safePos));
						if (resolved.parent.inlineContent) {
							editor.view.dispatch(
								editor.view.state.tr.setSelection(TextSelection.create(doc, resolved.pos))
							);
						}
					}
				} catch (e) {
					console.warn('[RichTextInput] selectTemplate error:', e);
				}
			}, 0);
		}
	};

	/** Convert current editor HTML to the value format (Markdown or HTML). */
	function extractValue(editorInstance: Editor): string {
		if (!raw) {
			let text = turndownService
				.turndown(
					editorInstance
						.getHTML()
						.replace(/<p><\/p>/g, '<br/>')
						.replace(/ {2,}/g, (m) => m.replace(/ /g, '\u00a0'))
				)
				.replace(/\u00a0/g, ' ');
			if (!preserveBreaks) {
				text = text.replace(/<br\/>/g, '');
			}
			return text;
		}
		return editorInstance.getHTML();
	}

	/** Try parsing Markdown to HTML with retries. */
	async function tryParse(md: string, attempts = 3, interval = 100): Promise<string> {
		try {
			return marked.parse(md.replaceAll(`\n<br/>`, `<br/>`), { breaks: false });
		} catch (_error) {
			if (attempts <= 1) return md;
			await new Promise((resolve) => setTimeout(resolve, interval));
			return tryParse(md, attempts - 1, interval);
		}
	}

	/** Check if a resolved position is inside one of the given node types. */
	function isInsideNode(state: EditorState, nodeTypes: string[]): boolean {
		let current = state.selection.$head;
		while (current) {
			if (nodeTypes.includes(current.parent.type.name)) return true;
			if (!current.depth) break;
			current = state.doc.resolve(current.before());
		}
		return false;
	}

	onMount(async () => {
		if (preserveBreaks) {
			turndownService.addRule('preserveBreaks', {
				filter: 'br',
				replacement: function (_content: string) {
					return '<br/>';
				}
			});
		}

		let content = value;
		if (!raw) {
			content = await tryParse(value);
		}

		editor = new Editor({
			element: element,
			extensions: [
				StarterKit.configure({ codeBlock: false }),
				CodeBlockLowlight.configure({ lowlight }),
				Highlight,
				Typography,
				Placeholder.configure({ placeholder }),
				...(autocomplete
					? [
							AIAutocompletion.configure({
								generateCompletion: async (text: string) => {
									if (text.trim().length === 0) return null;
									const suggestion = await generateAutoCompletion(text).catch(() => null);
									if (!suggestion || suggestion.trim().length === 0) return null;
									return suggestion;
								}
							})
						]
					: [])
			],
			content: content,
			autofocus: messageInput ? true : false,
			onTransaction: ({ editor: editorInstance }) => {
				if (_destroyed) return;
				queueMicrotask(() => {
					if (_destroyed) return;
					editor = editorInstance;

					const newValue = extractValue(editorInstance);
					if (value !== newValue) {
						value = newValue;
						onchange?.({ detail: { value } });

						if (!raw && editorInstance.isActive('paragraph') && value === '') {
							editorInstance.commands.clearContent();
						}
					}
				});
			},
			editorProps: {
				attributes: { id },
				handleDOMEvents: {
					compositionstart: (_view, event) => {
						oncompositionstart(event);
						return false;
					},
					compositionend: (_view, event) => {
						oncompositionend(event);
						return false;
					},
					focus: (_view, event) => {
						onfocus?.({ detail: { event } });
						return false;
					},
					keyup: (_view, event) => {
						onkeyup?.({ detail: { event } });
						return false;
					},
					keydown: (view, event) => {
						if (messageInput) {
							if (event.key === 'Tab') {
								const handled = selectNextTemplate(view.state, view.dispatch);
								if (handled) {
									event.preventDefault();
									return true;
								}
							}

							if (event.key === 'Enter') {
								const isInCodeBlock = isInsideNode(view.state, ['codeBlock']);
								const isInList = isInsideNode(view.state, [
									'listItem',
									'bulletList',
									'orderedList'
								]);
								const isInHeading = isInsideNode(view.state, ['heading']);

								if (isInCodeBlock || isInList || isInHeading) {
									return false;
								}
							}

							if (shiftEnter) {
								if (event.key === 'Enter' && event.shiftKey && !event.ctrlKey && !event.metaKey) {
									editor?.commands.setHardBreak();
									view.dispatch(view.state.tr.scrollIntoView());
									event.preventDefault();
									return true;
								}
								if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey && !event.metaKey) {
									onkeydown?.({ detail: { event } });
									event.preventDefault();
									return true;
								}
							}
						}
						onkeydown?.({ detail: { event } });
						return false;
					},
					paste: (view, event) => {
						if (event.clipboardData) {
							const plainText = event.clipboardData.getData('text/plain');
							if (plainText) {
								if (largeTextAsFile && plainText.length > PASTED_TEXT_CHARACTER_LIMIT) {
									onpaste?.({ detail: { event } });
									event.preventDefault();
									return true;
								}
								return false;
							}

							const hasImageFile = Array.from(event.clipboardData.files).some((file) =>
								file.type.startsWith('image/')
							);
							const hasImageItem = Array.from(event.clipboardData.items).some((item) =>
								item.type.startsWith('image/')
							);

							if (hasImageFile || hasImageItem) {
								onpaste?.({ detail: { event } });
								event.preventDefault();
								return true;
							}
						}
						view.dispatch(view.state.tr.scrollIntoView());
						return false;
					}
				}
			}
		});

		if (messageInput) {
			selectTemplate();
		}

		// Native input fallback listener
		const handleNativeInput = () => {
			const fallbackText = (element?.textContent ?? '').trim();
			try {
				if (editor) {
					const text = extractValue(editor);
					if (value !== text) {
						value = text;
						onchange?.({ detail: { value } });
					}
				} else {
					if (value !== fallbackText) {
						value = fallbackText;
						onchange?.({ detail: { value } });
					}
				}
			} catch (e) {
				console.warn('[RichTextInput] native input handler fallback:', e);
				if (value !== fallbackText) {
					value = fallbackText;
					onchange?.({ detail: { value } });
				}
			}
		};

		element?.addEventListener('input', handleNativeInput);
		cleanupNativeInput = () => element?.removeEventListener('input', handleNativeInput);
	});

	onDestroy(() => {
		_destroyed = true;
		cleanupNativeInput();
		if (editor) {
			editor.destroy();
		}
	});

	// Sync external value changes into the editor
	$effect(() => {
		if (!editor) return;
		const currentEditorValue = raw ? editor.getHTML() : extractValue(editor);

		if (value !== currentEditorValue) {
			if (raw || preserveBreaks) {
				editor.commands.setContent(value);
			} else {
				editor.commands.setContent(
					marked.parse(value.replaceAll(`\n<br/>`, `<br/>`), { breaks: false })
				);
			}
			selectTemplate();
		}
	});
</script>

<div bind:this={element} class="relative w-full min-w-full h-full min-h-fit {className}"></div>
