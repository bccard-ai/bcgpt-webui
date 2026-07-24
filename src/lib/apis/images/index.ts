import { imagesClient } from '$lib/apis/client';

export const getConfig = async (token: string = '') => imagesClient.get('/config', { token });

export const updateConfig = async (token: string = '', config: object) =>
	imagesClient.post('/config/update', { ...config }, { token });

export const verifyConfigUrl = async (token: string = '') =>
	imagesClient.get('/config/url/verify', { token });

export const getImageGenerationConfig = async (token: string = '') =>
	imagesClient.get('/image/config', { token });

export const updateImageGenerationConfig = async (token: string = '', config: object) =>
	imagesClient.post('/image/config/update', { ...config }, { token });

export const getImageGenerationModels = async (token: string = '') =>
	imagesClient.get('/models', { token });

export const imageGenerations = async (token: string = '', prompt: string) =>
	imagesClient.post('/generations', { prompt }, { token, timeout: 120_000 });
