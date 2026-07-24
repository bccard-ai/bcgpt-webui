export type ModelProvider =
	| 'ollama'
	| 'openai'
	| 'gemini'
	| 'claude'
	| 'vllm'
	| 'deepseek'
	| 'perplexity'
	| 'glm'
	| 'unknown';

const PROVIDER_PATTERNS: { pattern: RegExp; provider: ModelProvider }[] = [
	{ pattern: /^(gpt-|o[13]-|chatgpt-|dall-e-|text-|davinci-|curie-|babbage-|ada-)/i, provider: 'openai' },
	{ pattern: /^(gemini-|models\/gemini-)/i, provider: 'gemini' },
	{ pattern: /^claude-/i, provider: 'claude' },
	{ pattern: /^deepseek-/i, provider: 'deepseek' },
	{ pattern: /^(sonar|pplx)/i, provider: 'perplexity' },
	{ pattern: /^glm-/i, provider: 'glm' }
];

const OWNED_BY_TO_PROVIDER: Record<string, ModelProvider> = {
	ollama: 'ollama',
	openai: 'openai',
	gemini: 'gemini',
	claude: 'claude',
	deepseek: 'deepseek',
	perplexity: 'perplexity',
	glm: 'glm',
	vllm: 'vllm'
};

export function getModelProvider(model: {
	id: string;
	owned_by?: string;
	direct?: boolean;
}): ModelProvider {
	const ownedBy = model.owned_by?.toLowerCase() ?? '';
	if (ownedBy in OWNED_BY_TO_PROVIDER) {
		return OWNED_BY_TO_PROVIDER[ownedBy];
	}

	const modelId = model.id.toLowerCase();
	for (const { pattern, provider } of PROVIDER_PATTERNS) {
		if (pattern.test(modelId)) {
			return provider;
		}
	}

	return 'unknown';
}

const PROVIDER_ICON_MAP: Record<ModelProvider, string> = {
	ollama: '/static/providers/ollama.svg',
	openai: '/static/providers/openai.svg',
	gemini: '/static/providers/gemini.svg',
	claude: '/static/providers/claude.svg',
	vllm: '/static/providers/vllm.svg',
	deepseek: '/static/providers/deepseek.svg',
	perplexity: '/static/providers/perplexity.svg',
	glm: '/static/providers/glm.svg',
	unknown: '/static/favicon.png'
};

export function getProviderIconPath(provider: ModelProvider): string {
	return PROVIDER_ICON_MAP[provider];
}

const DEFAULT_FAVICON = '/static/favicon.png';

export function getModelIconUrl(model: {
	id: string;
	owned_by?: string;
	direct?: boolean;
	profileImageUrl?: string;
}): string {
	const profileImage = model.profileImageUrl;

	if (profileImage && profileImage !== DEFAULT_FAVICON) {
		return profileImage;
	}

	return getProviderIconPath(getModelProvider(model));
}
