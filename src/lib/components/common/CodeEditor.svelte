<script lang="ts">
	import { basicSetup, EditorView } from 'codemirror';
	import { keymap, placeholder } from '@codemirror/view';
	import { Compartment, EditorState } from '@codemirror/state';
	import { acceptCompletion } from '@codemirror/autocomplete';
	import { indentWithTab } from '@codemirror/commands';
	import { indentUnit, LanguageDescription } from '@codemirror/language';
	import { languages } from '@codemirror/language-data';
	import { oneDark } from '@codemirror/theme-one-dark';
	import { onMount, getContext, tick } from 'svelte';
	import { formatPythonCode } from '$lib/apis/utils';
	import { toast } from 'svelte-sonner';
	import type { i18n as i18nType } from 'i18next';
	import type { Writable } from 'svelte/store';

	const i18n: Writable<i18nType> = getContext<Writable<i18nType>>('i18n');

	/**
	 * CodeEditor — CodeMirror 6-based code editor with language support, dark mode, and formatting.
	 *
	 * @example
	 * ```svelte
	 * <CodeEditor bind:value lang="python" onSave={handleSave} />
	 * ```
	 *
	 * @props value - Bindable editor content
	 * @props boilerplate - Default content when value is empty
	 * @props lang - Language for syntax highlighting
	 * @props onSave - Called on Ctrl/Cmd+S
	 * @props id - HTML id for the editor container
	 */
	interface Props {
		/** Default content inserted when value is empty. */
		boilerplate?: string;
		/** Bindable editor content. */
		value?: string;
		/** Called on Ctrl/Cmd+S. */
		onSave?: () => void;
		/** Called when the editor content changes. */
		onchange?: (value: string) => void;
		/** HTML id for the editor container div. */
		id?: string;
		/** Language for syntax highlighting. */
		lang?: string;
		/**
		 * Read-only viewer mode for chat code blocks: hides line numbers / fold
		 * gutter, disables editing, and applies the Claude-like chrome theme.
		 * Defaults to false so ToolkitEditor / FunctionEditor stay editable.
		 */
		viewer?: boolean;
	}

	let {
		boilerplate = '',
		value = $bindable(''),
		onSave = () => {},
		onchange = () => {},
		id = '',
		lang = '',
		viewer = false
	}: Props = $props();

	let _value = '';
	let codeEditor: EditorView | null = null;

	let isDarkMode = false;
	let editorTheme = new Compartment();
	let editorLanguage = new Compartment();

	/** Focus the editor. */
	export const focus = () => {
		codeEditor?.focus();
	};

	/** Format the current content as Python code via the backend API. */
	export const formatPythonCodeHandler = async (): Promise<boolean> => {
		if (!codeEditor) return false;
		const res = await formatPythonCode('', _value).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		if (res && res.code) {
			const formattedCode = res.code;
			codeEditor.dispatch({
				changes: [{ from: 0, to: codeEditor.state.doc.length, insert: formattedCode }]
			});
			_value = formattedCode;
			onchange(_value);
			await tick();
			toast.success($i18n.t('Code formatted successfully'));
			return true;
		}
		return false;
	};

	/** Find minimal diff-based changes between two strings. */
	function findChanges(
		oldStr: string,
		newStr: string
	): { from: number; to: number; insert: string }[] {
		const changes: { from: number; to: number; insert: string }[] = [];
		let oldIndex = 0;
		let newIndex = 0;

		while (oldIndex < oldStr.length || newIndex < newStr.length) {
			if (oldStr[oldIndex] !== newStr[newIndex]) {
				const start = oldIndex;
				while (oldIndex < oldStr.length && oldStr[oldIndex] !== newStr[newIndex]) {
					oldIndex++;
				}
				while (newIndex < newStr.length && newStr[newIndex] !== oldStr[start]) {
					newIndex++;
				}
				changes.push({
					from: start,
					to: oldIndex,
					insert: newStr.substring(start, newIndex)
				});
			} else {
				oldIndex++;
				newIndex++;
			}
		}
		return changes;
	}

	/** Update the CodeMirror doc when the external value changes. */
	const updateValue = () => {
		if (_value !== value) {
			const changes = findChanges(_value, value);
			_value = value;
			if (codeEditor && changes.length > 0) {
				codeEditor.dispatch({ changes });
			}
		}
	};

	/** Load a CodeMirror language extension by alias. */
	const getLang = async () => {
		const language = languages.find((l) => l.alias.includes(lang));
		return await language?.load();
	};

	/** Reconfigure the language compartment. */
	const setLanguage = async () => {
		const language = await getLang();
		if (language && codeEditor) {
			codeEditor.dispatch({
				effects: editorLanguage.reconfigure(language)
			});
		}
	};

	// Register HCL language support
	languages.push(
		LanguageDescription.of({
			name: 'HCL',
			extensions: ['hcl', 'tf'],
			load() {
				return import('codemirror-lang-hcl').then((m) => m.hcl());
			}
		})
	);

	/**
	 * Chrome overrides for the read-only chat viewer: hide gutters (line numbers
	 * + fold gutter), neutralize the active-line highlight, drop the cursor and
	 * focus outline, and set the Claude-like font metrics + content padding.
	 * Neutral w.r.t. light/dark — token colors still come from oneDark (dark)
	 * or CodeMirror defaults (light) via the editorTheme compartment below.
	 */
	const viewerChromeTheme = EditorView.theme({
		'&': { fontSize: '13px', height: 'auto' },
		'&.cm-focused': { outline: 'none' },
		'.cm-scroller': {
			fontFamily: 'var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace)'
		},
		'.cm-content': { padding: '12px 16px', lineHeight: '1.6' },
		'.cm-line': { padding: '0' },
		'.cm-gutters': { display: 'none' },
		'.cm-foldGutter': { display: 'none' },
		'.cm-activeLine': { backgroundColor: 'transparent' },
		'.cm-activeLineGutter': { backgroundColor: 'transparent' },
		'.cm-cursor': { display: 'none' }
	});

	onMount(() => {
		if (value === '') {
			value = boilerplate;
		}
		_value = value;

		isDarkMode = document.documentElement.classList.contains('dark');

		const container = document.getElementById(`code-textarea-${id}`);
		if (!container) return;

		// Built inside onMount so the `viewer` prop is read once at mount; CodeMirror
		// is created a single time and `viewer` is constant for a given instance.
		const extensions = viewer
			? [
					basicSetup,
					EditorView.editable.of(false),
					EditorState.readOnly.of(true),
					viewerChromeTheme,
					editorTheme.of([]),
					editorLanguage.of([])
				]
			: [
					basicSetup,
					keymap.of([{ key: 'Tab', run: acceptCompletion }, indentWithTab]),
					indentUnit.of('    '),
					placeholder($i18n.t('Enter your code here...')),
					EditorView.updateListener.of((e) => {
						if (e.docChanged) {
							_value = e.state.doc.toString();
							onchange(_value);
						}
					}),
					editorTheme.of([]),
					editorLanguage.of([])
				];

		codeEditor = new EditorView({
			state: EditorState.create({
				doc: _value,
				extensions
			}),
			parent: container
		});

		if (isDarkMode) {
			codeEditor.dispatch({ effects: editorTheme.reconfigure(oneDark) });
		}

		// Watch for dark mode class changes on <html>
		const observer = new MutationObserver((mutations) => {
			for (const mutation of mutations) {
				if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
					const newDark = document.documentElement.classList.contains('dark');
					if (newDark !== isDarkMode) {
						isDarkMode = newDark;
						codeEditor?.dispatch({
							effects: editorTheme.reconfigure(newDark ? oneDark : [])
						});
					}
				}
			}
		});

		observer.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ['class']
		});

		const keydownHandler = async (e: KeyboardEvent) => {
			if ((e.ctrlKey || e.metaKey) && e.key === 's') {
				e.preventDefault();
				onSave();
			}
			if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'f') {
				e.preventDefault();
				await formatPythonCodeHandler();
			}
		};

		document.addEventListener('keydown', keydownHandler);

		return () => {
			observer.disconnect();
			document.removeEventListener('keydown', keydownHandler);
		};
	});

	$effect(() => {
		if (value) updateValue();
	});
	$effect(() => {
		if (lang) setLanguage();
	});
</script>

<div id="code-textarea-{id}" class="h-full w-full"></div>
