import { apiClient } from '$lib/apis/client';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

export const getConfig = async (token: string = '') =>
	apiClient.get('/evaluations/config', { token });

export const updateConfig = async (token: string, config: object) =>
	apiClient.post('/evaluations/config', { ...config }, { token });

// ---------------------------------------------------------------------------
// Feedback
// ---------------------------------------------------------------------------

export const getAllFeedbacks = async (token: string = '') =>
	apiClient.get('/evaluations/feedbacks/all', { token });

export const exportAllFeedbacks = async (token: string = '') =>
	apiClient.get('/evaluations/feedbacks/all/export', { token });

export const createNewFeedback = async (token: string, feedback: object) =>
	apiClient.post('/evaluations/feedback', { ...feedback }, { token });

export const getFeedbackById = async (token: string, feedbackId: string) =>
	apiClient.get(`/evaluations/feedback/${feedbackId}`, { token });

export const updateFeedbackById = async (token: string, feedbackId: string, feedback: object) =>
	apiClient.post(`/evaluations/feedback/${feedbackId}`, { ...feedback }, { token });

export const deleteFeedbackById = async (token: string, feedbackId: string) =>
	apiClient.del(`/evaluations/feedback/${feedbackId}`, undefined, { token });
