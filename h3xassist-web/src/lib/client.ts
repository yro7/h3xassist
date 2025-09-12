/**
 * Auto-generated API client using openapi-fetch
 * Fully typed based on OpenAPI schema
 */

import createClient from "openapi-fetch";
import type { paths } from "../types/api";
import { config } from "../config/env";

// Create fully typed API client
export const client = createClient<paths>({
  baseUrl: config.apiUrl,
});

// Configure default headers
client.use({
  async onRequest({ request }) {
    request.headers.set("Content-Type", "application/json");
    return request;
  },
});

// Error handling middleware
client.use({
  async onResponse({ response }) {
    if (!response.ok) {
      // Let the calling code handle errors
      throw response;
    }
    return response;
  },
});

export default client;
