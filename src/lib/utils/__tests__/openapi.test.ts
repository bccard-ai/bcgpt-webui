/**
 * @fileoverview Tests for OpenAPI specification to tool-payload conversion.
 *
 * @module utils/__tests__/openapi
 */

import { describe, expect, it } from 'vitest';
import { convertOpenApiToToolPayload } from '../openapi';

describe('convertOpenApiToToolPayload', () => {
	it('resolves nested request body refs and array item refs', () => {
		const payload = convertOpenApiToToolPayload({
			paths: {
				'/pets': {
					post: {
						operationId: 'createPet',
						summary: 'Create a pet',
						requestBody: {
							content: {
								'application/json': {
									schema: { $ref: '#/components/schemas/PetInput' }
								}
							}
						}
					}
				}
			},
			components: {
				schemas: {
					PetInput: {
						type: 'object',
						required: ['name', 'owner'],
						properties: {
							name: { type: 'string', description: 'Pet name' },
							owner: { $ref: '#/components/schemas/Owner' },
							tags: {
								type: 'array',
								items: { $ref: '#/components/schemas/Tag' }
							}
						}
					},
					Owner: {
						type: 'object',
						required: ['id'],
						properties: {
							id: { type: 'string' },
							address: { $ref: '#/components/schemas/Address' }
						}
					},
					Address: {
						type: 'object',
						properties: {
							city: { type: 'string' }
						}
					},
					Tag: {
						type: 'object',
						properties: {
							label: { type: 'string' }
						}
					}
				}
			}
		});

		expect(payload).toEqual([
			{
				type: 'function',
				name: 'createPet',
				description: 'Create a pet',
				parameters: {
					type: 'object',
					properties: {
						name: { type: 'string', description: 'Pet name' },
						owner: {
							type: 'object',
							required: ['id'],
							properties: {
								id: { type: 'string' },
								address: {
									type: 'object',
									required: [],
									properties: {
										city: { type: 'string' }
									}
								}
							}
						},
						tags: {
							type: 'array',
							items: {
								type: 'object',
								required: [],
								properties: {
									label: { type: 'string' }
								}
							}
						}
					},
					required: ['name', 'owner']
				}
			}
		]);
	});

	it('resolves repeated refs in sibling properties independently', () => {
		const [tool] = convertOpenApiToToolPayload({
			paths: {
				'/orders': {
					post: {
						operationId: 'createOrder',
						requestBody: {
							content: {
								'application/json': {
									schema: { $ref: '#/components/schemas/Order' }
								}
							}
						}
					}
				}
			},
			components: {
				schemas: {
					Order: {
						type: 'object',
						properties: {
							billingAddress: { $ref: '#/components/schemas/Address' },
							shippingAddress: { $ref: '#/components/schemas/Address' }
						}
					},
					Address: {
						type: 'object',
						properties: {
							line1: { type: 'string' }
						}
					}
				}
			}
		});

		expect(tool.parameters.properties?.billingAddress).toEqual(
			tool.parameters.properties?.shippingAddress
		);
		expect(tool.parameters.properties?.billingAddress).toEqual({
			type: 'object',
			required: [],
			properties: {
				line1: { type: 'string' }
			}
		});
	});

	it('cuts circular refs at the recursive branch', () => {
		const [tool] = convertOpenApiToToolPayload({
			paths: {
				'/nodes': {
					post: {
						operationId: 'createNode',
						requestBody: {
							content: {
								'application/json': {
									schema: { $ref: '#/components/schemas/Node' }
								}
							}
						}
					}
				}
			},
			components: {
				schemas: {
					Node: {
						type: 'object',
						properties: {
							id: { type: 'string' },
							child: { $ref: '#/components/schemas/Node' },
							children: {
								type: 'array',
								items: { $ref: '#/components/schemas/Node' }
							}
						}
					}
				}
			}
		});

		expect(tool.parameters.properties?.child).toEqual({});
		expect(tool.parameters.properties?.children).toEqual({
			type: 'array',
			items: {}
		});
	});
});
