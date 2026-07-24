import { v4 as uuidv4 } from 'uuid';

export const convertMessagesToHistory = (messages) => {
	const history = {
		messages: {},
		currentId: null
	};

	let parentMessageId = null;
	let messageId = null;

	for (const message of messages) {
		messageId = uuidv4();

		if (parentMessageId !== null) {
			history.messages[parentMessageId].childrenIds = [
				...history.messages[parentMessageId].childrenIds,
				messageId
			];
		}

		history.messages[messageId] = {
			...message,
			id: messageId,
			parentId: parentMessageId,
			childrenIds: []
		};

		parentMessageId = messageId;
	}

	history.currentId = messageId;
	return history;
};

export const createMessagesList = (history, messageId) => {
	if (messageId === null) {
		return [];
	}

	const message = history.messages[messageId];
	if (message?.parentId) {
		return [...createMessagesList(history, message.parentId), message];
	} else {
		return [message];
	}
};
