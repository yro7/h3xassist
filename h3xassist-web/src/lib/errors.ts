/**
 * Error handling utilities for H3xAssist API
 */

export class APIError extends Error {
  public status: number;
  public details?: any;

  constructor(message: string, status: number, details?: any) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.details = details;
  }
}

export interface ErrorResponse {
  error: string;
  details?: any;
  status?: number;
}

export function parseAPIError(error: unknown): string {
  if (error instanceof APIError) {
    // Handle specific API error codes
    switch (error.status) {
      case 400:
        return (
          error.details?.detail || error.message || "Invalid request parameters"
        );
      case 401:
        return "Authentication required";
      case 403:
        return "Access denied";
      case 404:
        return "Resource not found";
      case 409:
        return error.details?.detail || "Conflict - resource already exists";
      case 422:
        // Validation errors from FastAPI
        if (error.details?.detail && Array.isArray(error.details.detail)) {
          const messages = error.details.detail.map((err: any) => {
            const field = err.loc?.join(".") || "field";
            return `${field}: ${err.msg}`;
          });
          return messages.join(", ");
        }
        return error.details?.detail || "Validation error";
      case 500:
        return "Server error - please try again later";
      case 503:
        return "Service temporarily unavailable";
      default:
        return error.message || `Request failed with status ${error.status}`;
    }
  }

  if (error instanceof Error) {
    // Network errors
    if (error.message.includes("fetch")) {
      return "Network error - unable to connect to server";
    }
    return error.message;
  }

  if (typeof error === "string") {
    return error;
  }

  return "An unexpected error occurred";
}

export function isNetworkError(error: unknown): boolean {
  return (
    error instanceof Error &&
    (error.message.includes("fetch") ||
      error.message.includes("network") ||
      error.message.includes("ECONNREFUSED"))
  );
}

export function isValidationError(error: unknown): boolean {
  return error instanceof APIError && error.status === 422;
}

export function isAuthError(error: unknown): boolean {
  return (
    error instanceof APIError && (error.status === 401 || error.status === 403)
  );
}

export function handleAPIError(
  error: unknown,
  fallbackMessage?: string,
): string {
  const message = parseAPIError(error);
  console.error("API Error:", error);
  return fallbackMessage ? `${fallbackMessage}: ${message}` : message;
}
