import { audioClient } from '$lib/apis/client';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export const getAudioConfig = async (token: string) => audioClient.get('/config', { token });

type OpenAIConfigForm = {
	url: string;
	key: string;
	model: string;
	speaker: string;
};

export const updateAudioConfig = async (token: string, payload: OpenAIConfigForm) =>
	audioClient.post('/config/update', { ...payload }, { token });

// ---------------------------------------------------------------------------
// Transcription & synthesis
// ---------------------------------------------------------------------------

export const transcribeAudio = async (token: string, file: File) => {
	const data = new FormData();
	data.append('file', file);
	return audioClient.post('/transcriptions', data, { token });
};

export const synthesizeOpenAISpeech = async (
	token: string = '',
	speaker: string = 'alloy',
	text: string = '',
	model?: string
) =>
	audioClient.post<Response>(
		'/speech',
		{ input: text, voice: speaker, ...(model && { model }) },
		{ token, rawResponse: true }
	);

// ---------------------------------------------------------------------------
// Models & voices
// ---------------------------------------------------------------------------

interface AvailableModelsResponse {
	models: { name: string; id: string }[] | { id: string }[];
}

export const getModels = async (token: string = '') =>
	audioClient.get<AvailableModelsResponse>('/models', { token });

export const getVoices = async (token: string = '') => audioClient.get('/voices', { token });
