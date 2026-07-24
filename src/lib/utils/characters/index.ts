/**
 * @fileoverview Character card parser for multiple AI character formats.
 *
 * Supports:
 * - **Text Generation Character** (JSON)
 * - **TavernAI Character** (JSON)
 * - **CharacterAI Character / History** (JSON)
 * - **PNG-embedded character cards** (tEXt chunk with base64 `chara` field)
 *
 * @module utils/characters
 */

import CRC32 from 'crc-32';

// ── Type definitions ──────────────────────────────────────────────────

/** Parsed character data extracted from any supported format. */
type CharacterData = {
	name: string | undefined;
	summary: string | undefined;
	personality: string | undefined;
	scenario: string | undefined;
	greeting: string | undefined;
	examples: string | undefined;
};

/** Result of parsing a character file. */
type ParsedCharacter = {
	file: File;
	json: Record<string, unknown>;
	image?: string;
	formats: string[];
	character: CharacterData;
};

/** Internal representation of a PNG chunk. */
type PngChunk = {
	type: string;
	data: Uint8Array;
	crc: number;
};

/** Decoded tEXt chunk entry. */
type TextChunkEntry = {
	keyword: string;
	text: string;
};

// ── Public API ────────────────────────────────────────────────────────

/**
 * Parse a character file (JSON or PNG) into structured data.
 *
 * @param file - The uploaded file to parse.
 * @returns Parsed character data including detected format and extracted fields.
 * @throws When the file type is unsupported or parsing fails.
 */
export const parseFile = async (file: File): Promise<ParsedCharacter> => {
	if (file.type === 'application/json') {
		return await parseJsonFile(file);
	} else if (file.type === 'image/png') {
		return await parsePngFile(file);
	} else {
		throw new Error('Unsupported file type');
	}
};

// ── JSON parsing ──────────────────────────────────────────────────────

/**
 * Parse a JSON character file.
 */
const parseJsonFile = async (file: File): Promise<ParsedCharacter> => {
	const text = await file.text();
	const json = JSON.parse(text);

	const character = extractCharacter(json);

	return {
		file,
		json,
		formats: detectFormats(json),
		character
	};
};

// ── PNG parsing ───────────────────────────────────────────────────────

/**
 * Parse a PNG character card with an embedded `chara` tEXt chunk.
 */
const parsePngFile = async (file: File): Promise<ParsedCharacter> => {
	const arrayBuffer = await file.arrayBuffer();
	const text = parsePngText(arrayBuffer);
	const json = JSON.parse(text);

	const image = URL.createObjectURL(file);
	const character = extractCharacter(json);

	return {
		file,
		json,
		image,
		formats: detectFormats(json),
		character
	};
};

/**
 * Extract and decode the base64-encoded `chara` tEXt chunk from a PNG buffer.
 *
 * @param arrayBuffer - Raw PNG file bytes.
 * @returns Decoded JSON string from the `chara` chunk.
 * @throws When the chunk is missing or the base64 is invalid.
 */
const parsePngText = (arrayBuffer: ArrayBuffer): string => {
	const textChunkKeyword = 'chara';
	const chunks = readPngChunks(new Uint8Array(arrayBuffer));

	const textChunk = chunks
		.filter((chunk) => chunk.type === 'tEXt')
		.map((chunk) => decodeTextChunk(chunk.data))
		.find((entry) => entry.keyword === textChunkKeyword);

	if (!textChunk) {
		throw new Error(`No PNG text chunk named "${textChunkKeyword}" found`);
	}

	try {
		return new TextDecoder().decode(
			Uint8Array.from(atob(textChunk.text), (c) => c.charCodeAt(0))
		);
	} catch (e) {
		throw new Error('Unable to parse "chara" field as base64', e as Error);
	}
};

/**
 * Read all chunks from a PNG file buffer, validating CRC checksums.
 *
 * @param data - Raw PNG bytes.
 * @returns Array of parsed chunk objects.
 * @throws When the PNG signature is invalid or a CRC mismatch is found.
 */
const readPngChunks = (data: Uint8Array): PngChunk[] => {
	const isValidPng =
		data[0] === 0x89 &&
		data[1] === 0x50 &&
		data[2] === 0x4e &&
		data[3] === 0x47 &&
		data[4] === 0x0d &&
		data[5] === 0x0a &&
		data[6] === 0x1a &&
		data[7] === 0x0a;

	if (!isValidPng) throw new Error('Invalid PNG file');

	const chunks: PngChunk[] = [];
	let offset = 8; // Skip PNG signature

	while (offset < data.length) {
		const length =
			(data[offset] << 24) | (data[offset + 1] << 16) | (data[offset + 2] << 8) | data[offset + 3];
		const type = String.fromCharCode.apply(null, data.slice(offset + 4, offset + 8) as unknown as number[]);
		const chunkData = data.slice(offset + 8, offset + 8 + length);
		const crc =
			(data[offset + 8 + length] << 24) |
			(data[offset + 8 + length + 1] << 16) |
			(data[offset + 8 + length + 2] << 8) |
			data[offset + 8 + length + 3];

		if (CRC32.buf(chunkData, CRC32.str(type)) !== crc) {
			throw new Error(`Invalid CRC for chunk type "${type}"`);
		}

		chunks.push({ type, data: chunkData, crc });
		offset += 12 + length;
	}

	return chunks;
};

/**
 * Decode a PNG `tEXt` chunk into its keyword and text components.
 *
 * @param data - Raw chunk data bytes.
 * @returns Object with `keyword` and `text` strings.
 */
const decodeTextChunk = (data: Uint8Array): TextChunkEntry => {
	let i = 0;
	const keyword: string[] = [];
	const text: string[] = [];

	for (; i < data.length && data[i] !== 0; i++) {
		keyword.push(String.fromCharCode(data[i]));
	}

	for (i++; i < data.length; i++) {
		text.push(String.fromCharCode(data[i]));
	}

	return { keyword: keyword.join(''), text: text.join('') };
};

// ── Character extraction ──────────────────────────────────────────────

/**
 * Extract standardised character fields from a JSON object by trying
 * multiple known key paths.
 *
 * @param json - Raw parsed JSON from a character file.
 * @returns Normalised character data.
 */
const extractCharacter = (json: Record<string, unknown>): CharacterData => {
	/**
	 * Try each key path (dot-separated) and return the first non-empty trimmed value.
	 */
	function getTrimmedValue(
		json: Record<string, unknown>,
		keys: string[]
	): string | undefined {
		return keys
			.map((key) => {
				const keyParts = key.split('.');
				let value: unknown = json;
				for (const part of keyParts) {
					if (value && typeof value === 'object' && (value as Record<string, unknown>)[part] != null) {
						value = (value as Record<string, unknown>)[part];
					} else {
						value = null;
						break;
					}
				}
				return value && typeof value === 'string' ? value.trim() : null;
			})
			.find((value): value is string => value != null);
	}

	const name = getTrimmedValue(json, ['char_name', 'name', 'data.name']);
	const summary = getTrimmedValue(json, ['personality', 'title', 'data.description']);
	const personality = getTrimmedValue(json, ['char_persona', 'description', 'data.personality']);
	const scenario = getTrimmedValue(json, ['world_scenario', 'scenario', 'data.scenario']);
	const greeting = getTrimmedValue(json, [
		'char_greeting',
		'greeting',
		'first_mes',
		'data.first_mes'
	]);
	const examples = getTrimmedValue(json, [
		'example_dialogue',
		'mes_example',
		'definition',
		'data.mes_example'
	]);

	return { name, summary, personality, scenario, greeting, examples };
};

/**
 * Detect which character card formats are present in the JSON.
 *
 * @param json - Raw parsed JSON.
 * @returns Array of format name strings.
 */
const detectFormats = (json: Record<string, unknown>): string[] => {
	const formats: string[] = [];

	if (
		json.char_name &&
		json.char_persona &&
		json.world_scenario &&
		json.char_greeting &&
		json.example_dialogue
	)
		formats.push('Text Generation Character');
	if (
		json.name &&
		json.personality &&
		json.description &&
		json.scenario &&
		json.first_mes &&
		json.mes_example
	)
		formats.push('TavernAI Character');
	if (
		json.character &&
		(json.character as Record<string, unknown>).name &&
		(json.character as Record<string, unknown>).title &&
		(json.character as Record<string, unknown>).description &&
		(json.character as Record<string, unknown>).greeting &&
		(json.character as Record<string, unknown>).definition
	)
		formats.push('CharacterAI Character');
	if (
		json.info &&
		(json.info as Record<string, unknown>).character &&
		((json.info as Record<string, unknown>).character as Record<string, unknown>).name &&
		((json.info as Record<string, unknown>).character as Record<string, unknown>).title &&
		((json.info as Record<string, unknown>).character as Record<string, unknown>).description &&
		((json.info as Record<string, unknown>).character as Record<string, unknown>).greeting
	)
		formats.push('CharacterAI History');

	return formats;
};
