/**
 * Auto-generated API type helpers from OpenAPI schema
 */

import type { paths, components } from "./api";

// Helper to extract response types
type GetResponse<T> = T extends {
  get: { responses: { 200: { content: { "application/json": infer R } } } };
}
  ? R
  : never;
type PostResponse<T> = T extends {
  post: { responses: { 200: { content: { "application/json": infer R } } } };
}
  ? R
  : never;

// Helper to extract request types
type PostBody<T> = T extends {
  post: { requestBody: { content: { "application/json": infer R } } };
}
  ? R
  : never;
type PutBody<T> = T extends {
  put: { requestBody: { content: { "application/json": infer R } } };
}
  ? R
  : never;

// Response types
export type RecordingListResponse = GetResponse<paths["/api/v1/recordings"]>;
export type RecordingResponse = RecordingListResponse extends (infer R)[]
  ? R
  : never;
export type CalendarSyncResponse = PostResponse<paths["/api/v1/calendar/sync"]>;
export type BrowserProfilesResponse = GetResponse<paths["/api/v1/profiles"]>;
export type BrowserProfile = BrowserProfilesResponse extends (infer P)[]
  ? P
  : never;
export type SettingsResponse = Record<string, any>;

// Request types
export type RecordingRequest = PostBody<paths["/api/v1/recordings"]>;
export type SettingsUpdateRequest = PutBody<paths["/api/v1/settings"]>;
export type SettingsUpdateResponse = {
  settings: Record<string, any>;
  restart_required: boolean;
  message: string;
};

export type SettingsSchemaResponse = Record<string, any>;

// Component schemas (if needed)
export type HTTPValidationError = components["schemas"]["HTTPValidationError"];

// Utility types
export type APIErrorResponse = {
  detail: string | HTTPValidationError["detail"];
};
