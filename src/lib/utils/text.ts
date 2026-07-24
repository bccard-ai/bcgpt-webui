import { TTS_RESPONSE_SPLIT } from '$lib/types';

export const findWordIndices = (text: string) => {
	const regex = /\[([^\]]+)\]/g;
	const matches = [];
	let match;

	while ((match = regex.exec(text)) !== null) {
		matches.push({
			word: match[1],
			startIndex: match.index,
			endIndex: regex.lastIndex - 1
		});
	}

	return matches;
};

export const removeLastWordFromString = (inputString: string, wordString: string) => {
	const lines = inputString.split('\n');
	const lastLine = lines.pop()!;
	const words = lastLine.split(' ');

	if (words.at(-1) === wordString || (wordString === '' && words.at(-1) === '\\#')) {
		words.pop();
	}

	let updatedLastLine = words.join(' ');

	if (updatedLastLine !== '') {
		updatedLastLine += ' ';
	}

	const resultString = [...lines, updatedLastLine].join('\n');

	return resultString;
};

export const removeFirstHashWord = (inputString: string) => {
	const words = inputString.split(' ');
	const index = words.findIndex((word) => word.startsWith('#'));

	if (index !== -1) {
		words.splice(index, 1);
	}

	return words.join(' ');
};

export const transformFileName = (fileName: string) => {
	const lowerCaseFileName = fileName.toLowerCase();
	const sanitizedFileName = lowerCaseFileName.replace(/[^\w\s]/g, '');
	const finalFileName = sanitizedFileName.replace(/\s+/g, '-');
	return finalFileName;
};

export const removeEmojis = (str: string) => {
	const emojiRegex = /[\uD800-\uDBFF][\uDC00-\uDFFF]|\uD83C[\uDC00-\uDFFF]|\uD83D[\uDC00-\uDE4F]/g;
	return str.replace(emojiRegex, '');
};

export const removeFormattings = (str: string) => {
	return str
		.replace(/(```[\s\S]*?```)/g, '')
		.replace(/^\|.*\|$/gm, '')
		.replace(/(?:\*\*|__)(.*?)(?:\*\*|__)/g, '$1')
		.replace(/(?:[*_])(.*?)(?:[*_])/g, '$1')
		.replace(/~~(.*?)~~/g, '$1')
		.replace(/`([^`]+)`/g, '$1')
		.replace(/!?\[([^\]]*)\](?:\([^)]+\)|\[[^\]]*\])/g, '$1')
		.replace(/^\[[^\]]+\]:\s*.*$/gm, '')
		.replace(/^#{1,6}\s+/gm, '')
		.replace(/^\s*[-*+]\s+/gm, '')
		.replace(/^\s*(?:\d+\.)\s+/gm, '')
		.replace(/^\s*>[> ]*/gm, '')
		.replace(/^\s*:\s+/gm, '')
		.replace(/\[\^[^\]]*\]/g, '')
		.replace(/[-*_~]/g, '')
		.replace(/\n{2,}/g, '\n');
};

export const cleanText = (content: string) => {
	return removeFormattings(removeEmojis(content.trim()));
};

export const removeDetails = (content: string, types: string[]) => {
	for (const type of types) {
		content = content.replace(
			new RegExp(`<details\\s+type="${type}"[^>]*>.*?<\\/details>`, 'gis'),
			''
		);
	}
	return content;
};

const codeBlockRegex = /```[\s\S]*?```/g;

export const extractSentences = (text: string) => {
	const codeBlocks: string[] = [];
	let index = 0;

	text = text.replace(codeBlockRegex, (match) => {
		const placeholder = `\u0000${index}\u0000`;
		codeBlocks[index++] = match;
		return placeholder;
	});

	let sentences = text.split(/(?<=[.!?])\s+/);

	sentences = sentences.map((sentence) => {
		// eslint-disable-next-line no-control-regex
		return sentence.replace(/\u0000(\d+)\u0000/g, (_, idx) => codeBlocks[idx]);
	});

	return sentences.map(cleanText).filter(Boolean);
};

export const extractParagraphsForAudio = (text: string) => {
	const codeBlocks: string[] = [];
	let index = 0;

	text = text.replace(codeBlockRegex, (match) => {
		const placeholder = `\u0000${index}\u0000`;
		codeBlocks[index++] = match;
		return placeholder;
	});

	let paragraphs = text.split(/\n+/);

	paragraphs = paragraphs.map((paragraph) => {
		// eslint-disable-next-line no-control-regex
		return paragraph.replace(/\u0000(\d+)\u0000/g, (_, idx) => codeBlocks[idx]);
	});

	return paragraphs.map(cleanText).filter(Boolean);
};

export const extractSentencesForAudio = (text: string) => {
	return extractSentences(text).reduce((mergedTexts, currentText) => {
		const lastIndex = mergedTexts.length - 1;
		if (lastIndex >= 0) {
			const previousText = mergedTexts[lastIndex];
			const wordCount = previousText.split(/\s+/).length;
			const charCount = previousText.length;
			if (wordCount < 4 || charCount < 50) {
				mergedTexts[lastIndex] = previousText + ' ' + currentText;
			} else {
				mergedTexts.push(currentText);
			}
		} else {
			mergedTexts.push(currentText);
		}
		return mergedTexts;
	}, [] as string[]);
};

export const getMessageContentParts = (content: string, split_on: string = 'punctuation') => {
	content = removeDetails(content, ['reasoning', 'tool_calls']);
	const messageContentParts: string[] = [];

	switch (split_on) {
		default:
		case TTS_RESPONSE_SPLIT.PUNCTUATION:
			messageContentParts.push(...extractSentencesForAudio(content));
			break;
		case TTS_RESPONSE_SPLIT.PARAGRAPHS:
			messageContentParts.push(...extractParagraphsForAudio(content));
			break;
		case TTS_RESPONSE_SPLIT.NONE:
			messageContentParts.push(cleanText(content));
			break;
	}

	return messageContentParts;
};

export const getLineCount = (text: string | null | undefined): number => {
	return text ? text.split('\n').length : 0;
};
