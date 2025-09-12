/**
 * Environment configuration for H3xAssist
 */

export const config = {
  // Use relative URLs when built for production (static export)
  // When served from same origin, use relative paths
  apiUrl: process.env.NEXT_PUBLIC_API_URL || "",
  wsUrl:
    process.env.NEXT_PUBLIC_WS_URL ||
    (typeof window !== "undefined"
      ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/v1/ws`
      : "ws://localhost:8000/ws/updates"),
} as const;

// Validation in development
if (typeof window === "undefined" && process.env.NODE_ENV === "development") {
  console.log("H3xAssist Config:", config);
}
