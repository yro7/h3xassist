"use client";

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import { config } from "../config/env";

interface RefreshSignal {
  // Empty signal from backend - no resource field needed
}

interface WebSocketContextValue {
  isConnected: boolean;
  lastRefresh: RefreshSignal | null;
  connectionError: string | null;
  reconnect: () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | undefined>(
  undefined,
);

interface WebSocketProviderProps {
  children: React.ReactNode;
  wsUrl?: string;
}

export function WebSocketProvider({
  children,
  wsUrl = config.wsUrl,
}: WebSocketProviderProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<RefreshSignal | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [shouldReconnect, setShouldReconnect] = useState(true);

  const connect = useCallback(() => {
    if (ws?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const websocket = new WebSocket(wsUrl);

      websocket.onopen = () => {
        setIsConnected(true);
        setConnectionError(null);
      };

      websocket.onmessage = (event) => {
        try {
          const signal: RefreshSignal = JSON.parse(event.data);
          setLastRefresh(signal);
        } catch (error) {
          console.error("Failed to parse WebSocket message:", error);
        }
      };

      websocket.onclose = (event) => {
        setIsConnected(false);
        setWs(null);

        if (shouldReconnect && event.code !== 1000) {
          setConnectionError("Connection lost. Reconnecting...");
          setTimeout(connect, 3000);
        }
      };

      websocket.onerror = (error) => {
        console.error("WebSocket error:", error);
        setConnectionError("WebSocket connection failed");
        setIsConnected(false);
      };

      setWs(websocket);
    } catch (error) {
      console.error("Failed to create WebSocket:", error);
      setConnectionError("Failed to connect to WebSocket");
    }
  }, [wsUrl, ws, shouldReconnect]);

  const reconnect = useCallback(() => {
    if (ws) {
      ws.close();
    }
    setTimeout(connect, 100);
  }, [ws, connect]);

  useEffect(() => {
    connect();

    return () => {
      setShouldReconnect(false);
      if (ws) {
        ws.close();
      }
    };
  }, []);

  // Auto-reconnect when coming back online
  useEffect(() => {
    const handleOnline = () => {
      if (!isConnected) {
        connect();
      }
    };

    window.addEventListener("online", handleOnline);
    return () => window.removeEventListener("online", handleOnline);
  }, [isConnected, connect]);

  return (
    <WebSocketContext.Provider
      value={{
        isConnected,
        lastRefresh,
        connectionError,
        reconnect,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket(): WebSocketContextValue {
  const context = useContext(WebSocketContext);
  if (context === undefined) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }
  return context;
}

// Hook to listen for refresh signals
export function useWebSocketRefresh() {
  const { lastRefresh } = useWebSocket();

  return {
    shouldRefresh: !!lastRefresh,
    lastRefresh,
  };
}
