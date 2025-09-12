/**
 * Integration between React Query and WebSocket refresh signals
 */

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useWebSocketRefresh } from "../contexts/websocket-context";
// Note: Manual refresh system removed - React Query handles all refresh logic
import { recordingKeys } from "./useRecordings";

export function useQueryRefresh() {
  const queryClient = useQueryClient();
  const { lastRefresh } = useWebSocketRefresh();

  // WebSocket refresh integration - simple refresh all recordings
  useEffect(() => {
    if (!lastRefresh) return;

    console.log("🔄 Query refresh triggered - invalidating all recordings");
    // Since backend only sends empty refresh signals, refresh all recordings
    queryClient.invalidateQueries({ queryKey: recordingKeys.all });
  }, [lastRefresh, queryClient]);
}
