/**
 * @fileoverview OpenAPI specification to tool-payload converter.
 *
 * Recursively resolves `$ref` pointers, handles circular references, and
 * produces a flat list of function-call payloads compatible with LLM
 * tool-use interfaces.
 *
 * @module utils/openapi
 */

// ── OpenAPI type definitions ──────────────────────────────────────────

/** Schema node within an OpenAPI spec. */
type OpenApiSchema = {
	$ref?: string;
	type?: string;
	description?: string;
	properties?: Record<string, OpenApiSchema>;
	required?: string[];
	items?: OpenApiSchema;
};

/** Top-level components section containing shared schemas. */
type OpenApiComponents = {
	schemas?: Record<string, OpenApiSchema>;
};

/** A single API parameter (path, query, header, etc.). */
type OpenApiParameter = {
	name: string;
	required?: boolean;
	schema?: OpenApiSchema;
};

/** An operation within a path item. */
type OpenApiOperation = {
	operationId?: string;
	summary?: string;
	parameters?: OpenApiParameter[];
	requestBody?: {
		content?: Record<string, { schema?: OpenApiSchema }>;
	};
};

/** The root OpenAPI document. */
type OpenApiSpec = {
	paths?: Record<string, Record<string, OpenApiOperation>>;
	components?: OpenApiComponents;
};

// ── Tool payload type definitions ─────────────────────────────────────

/** JSON Schema node for tool parameters. */
type ToolSchema = {
	type?: string;
	description?: string;
	properties?: Record<string, ToolSchema>;
	required?: string[];
	items?: ToolSchema;
};

/** A single tool definition ready for LLM consumption. */
type ToolPayload = {
	type: 'function';
	name: string | undefined;
	description: string;
	parameters: ToolSchema;
};

// ── Internal helpers ──────────────────────────────────────────────────

/**
 * Recursively resolve an OpenAPI schema into a plain JSON Schema object.
 *
 * Circular `$ref` chains are detected and cut off by returning an empty
 * object at the recursive branch, preventing infinite loops.
 *
 * @param schemaRef - The schema node to resolve (may contain `$ref`).
 * @param components - Shared component schemas for `$ref` resolution.
 * @param resolvedSchemas - Set of already-visited schema names (cycle guard).
 * @returns A resolved `ToolSchema` object.
 */
function resolveSchema(
	schemaRef: OpenApiSchema | undefined,
	components: OpenApiComponents | undefined,
	resolvedSchemas = new Set<string>()
): ToolSchema {
	if (!schemaRef) return {};

	// Handle $ref pointers
	if (schemaRef['$ref']) {
		const refPath = schemaRef['$ref'];
		const schemaName = refPath.split('/').pop();
		if (!schemaName) {
			return {};
		}

		if (resolvedSchemas.has(schemaName)) {
			// Cut off circular references
			return {};
		}

		const referencedSchema = components?.schemas?.[schemaName];
		return resolveSchema(referencedSchema, components, new Set([...resolvedSchemas, schemaName]));
	}

	if (schemaRef.type) {
		const schemaObj: ToolSchema = { type: schemaRef.type };

		if (schemaRef.description) {
			schemaObj.description = schemaRef.description;
		}

		switch (schemaRef.type) {
			case 'object':
				schemaObj.properties = {};
				schemaObj.required = schemaRef.required || [];
				for (const [propName, propSchema] of Object.entries(schemaRef.properties || {})) {
					schemaObj.properties[propName] = resolveSchema(propSchema, components, resolvedSchemas);
				}
				break;

			case 'array':
				schemaObj.items = resolveSchema(schemaRef.items, components, resolvedSchemas);
				break;

			default:
				// Primitive types (string, integer, etc.) — no further resolution needed
				break;
		}
		return schemaObj;
	}

	// Fallback for schemas without an explicit type
	return {};
}

// ── Public API ────────────────────────────────────────────────────────

/**
 * Convert a full OpenAPI specification into an array of tool payloads.
 *
 * Each path + method combination becomes one tool entry with its parameters
 * extracted from both the `parameters` array and the `requestBody` schema.
 * Nested `$ref` pointers are resolved recursively.
 *
 * @param openApiSpec - A parsed OpenAPI v3 specification object.
 * @returns Array of `{ type, name, description, parameters }` tool definitions.
 */
export const convertOpenApiToToolPayload = (openApiSpec: OpenApiSpec): ToolPayload[] => {
	const toolPayload: ToolPayload[] = [];

	for (const [, methods] of Object.entries(openApiSpec.paths ?? {})) {
		for (const [, operation] of Object.entries(methods)) {
			const tool: ToolPayload = {
				type: 'function',
				name: operation.operationId,
				description: operation.summary || 'No description available.',
				parameters: {
					type: 'object',
					properties: {},
					required: []
				}
			};

			// Extract path and query parameters
			if (operation.parameters) {
				operation.parameters.forEach((param) => {
					const schema = param.schema ?? {};
					tool.parameters.properties = tool.parameters.properties ?? {};
					tool.parameters.required = tool.parameters.required ?? [];
					tool.parameters.properties[param.name] = {
						type: schema.type,
						description: schema.description || ''
					};

					if (param.required) {
						tool.parameters.required.push(param.name);
					}
				});
			}

			// Recursively resolve requestBody schema
			if (operation.requestBody) {
				const content = operation.requestBody.content;
				if (content && content['application/json']) {
					const requestSchema = content['application/json'].schema;
					const resolvedRequestSchema = resolveSchema(requestSchema, openApiSpec.components);

					if (resolvedRequestSchema.properties) {
						tool.parameters.properties = {
							...tool.parameters.properties,
							...resolvedRequestSchema.properties
						};

						if (resolvedRequestSchema.required) {
							tool.parameters.required = [
								...new Set([...(tool.parameters.required ?? []), ...resolvedRequestSchema.required])
							];
						}
					} else if (resolvedRequestSchema.type === 'array') {
						// Special case: root schema is an array
						tool.parameters = resolvedRequestSchema;
					}
				}
			}

			toolPayload.push(tool);
		}
	}

	return toolPayload;
};
