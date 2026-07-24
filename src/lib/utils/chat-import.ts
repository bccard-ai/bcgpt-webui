export const getImportOrigin = (_chats) => {
	// Check what external service chat imports are from
	if ('mapping' in _chats[0]) {
		return 'openai';
	}
	return 'bcgpt';
};

const convertOpenAIMessages = (convo) => {
	// Parse OpenAI chat messages and create chat dictionary for creating new chats
	const mapping = convo['mapping'];
	const messages = [];
	let currentId = '';
	let lastId = null;

	for (const message_id in mapping) {
		const message = mapping[message_id];
		currentId = message_id;
		try {
			if (
				messages.length == 0 &&
				(message['message'] == null ||
					(message['message']['content']['parts']?.[0] == '' &&
						message['message']['content']['text'] == null))
			) {
				// Skip chat messages with no content
				continue;
			} else {
				const new_chat = {
					id: message_id,
					parentId: lastId,
					childrenIds: message['children'] || [],
					role: message['message']?.['author']?.['role'] !== 'user' ? 'assistant' : 'user',
					content:
						message['message']?.['content']?.['parts']?.[0] ||
						message['message']?.['content']?.['text'] ||
						'',
					model: 'gpt-3.5-turbo',
					done: true,
					context: null
				};
				messages.push(new_chat);
				lastId = currentId;
			}
		} catch {
			// ignore
		}
	}

	const history: Record<PropertyKey, (typeof messages)[number]> = {};
	messages.forEach((obj) => (history[obj.id] = obj));

	const chat = {
		history: {
			currentId: currentId,
			messages: history // Need to convert this to not a list and instead a json object
		},
		models: ['gpt-3.5-turbo'],
		messages: messages,
		options: {},
		timestamp: convo['create_time'],
		title: convo['title'] ?? 'New Chat'
	};
	return chat;
};

const validateChat = (chat) => {
	// Because ChatGPT sometimes has features we can't use like DALL-E or might have corrupted messages, need to validate
	const messages = chat.messages;

	// Check if messages array is empty
	if (messages.length === 0) {
		return false;
	}

	// Last message's children should be an empty array
	const lastMessage = messages[messages.length - 1];
	if (lastMessage.childrenIds.length !== 0) {
		return false;
	}

	// First message's parent should be null
	const firstMessage = messages[0];
	if (firstMessage.parentId !== null) {
		return false;
	}

	// Every message's content should be a string
	for (const message of messages) {
		if (typeof message.content !== 'string') {
			return false;
		}
	}

	return true;
};

export const convertOpenAIChats = (_chats) => {
	// Create a list of dictionaries with each conversation from import
	const chats = [];
	let _failed = 0;
	for (const convo of _chats) {
		const chat = convertOpenAIMessages(convo);

		if (validateChat(chat)) {
			chats.push({
				id: convo['id'],
				user_id: '',
				title: convo['title'],
				chat: chat,
				timestamp: convo['create_time']
			});
		} else {
			_failed++;
		}
	}
	return chats;
};
