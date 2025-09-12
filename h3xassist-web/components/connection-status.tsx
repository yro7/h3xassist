"use client";

import { useWebSocket } from "@/src/contexts/websocket-context";

export function ConnectionStatus() {
  const { isConnected, connectionError } = useWebSocket();

  // Show status bar at the very top of the page
  if (!isConnected) {
    return (
      <div
        className={`fixed top-0 left-0 right-0 h-0.5 z-[100] ${
          connectionError ? "bg-red-500" : "bg-yellow-500"
        } animate-pulse`}
      />
    );
  }

  // Show green line for 2 seconds when connected, then hide
  return (
    <div
      className="fixed top-0 left-0 right-0 h-0.5 bg-green-500 z-[100] animate-pulse"
      style={{ animation: "fadeOut 2s ease-in-out forwards" }}
    >
      <style jsx>{`
        @keyframes fadeOut {
          0% {
            opacity: 1;
          }
          70% {
            opacity: 1;
          }
          100% {
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
}
