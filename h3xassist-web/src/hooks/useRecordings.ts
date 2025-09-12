/**
 * React Query hooks for Recordings API
 * Recordings now include all meeting functionality (events merged into recordings)
 */

import { useMemo, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { client } from "../lib/client";
import { useWebSocket } from "../contexts/websocket-context";
import type {
  RecordingResponse,
  RecordingListResponse,
  RecordingRequest,
} from "../types/helpers";

// Query Keys
export const recordingKeys = {
  all: ["recordings"] as const,
  lists: () => [...recordingKeys.all, "list"] as const,
  list: () => [...recordingKeys.lists()] as const,
  details: () => [...recordingKeys.all, "detail"] as const,
  detail: (id: string) => [...recordingKeys.details(), id] as const,
};

// Queries
export function useRecordings() {
  const queryClient = useQueryClient();
  const { lastRefresh, isConnected } = useWebSocket();

  // Invalidate recordings when WebSocket refresh signal is received
  useEffect(() => {
    if (lastRefresh) {
      queryClient.invalidateQueries({ queryKey: recordingKeys.lists() });
    }
  }, [lastRefresh, queryClient]);

  // Invalidate recordings when WebSocket connects (to get latest data)
  useEffect(() => {
    if (isConnected) {
      queryClient.invalidateQueries({ queryKey: recordingKeys.lists() });
    }
  }, [isConnected, queryClient]);

  return useQuery({
    queryKey: recordingKeys.list(),
    queryFn: async () => {
      const { data, error } = await client.GET("/api/v1/recordings");
      if (error) throw error;
      return data;
    },
  });
}

export function useRecording(recordingId: string) {
  return useQuery({
    queryKey: recordingKeys.detail(recordingId),
    queryFn: async () => {
      const { data, error } = await client.GET(
        "/api/v1/recordings/{recording_id}",
        {
          params: { path: { recording_id: recordingId } },
        },
      );
      if (error) throw error;
      return data;
    },
    enabled: !!recordingId,
  });
}

// Mutations
export function useCreateRecording() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (recording: RecordingRequest) => {
      const { data, error } = await client.POST("/api/v1/recordings", {
        body: recording,
      });
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      // Invalidate and refetch recordings
      queryClient.invalidateQueries({ queryKey: recordingKeys.lists() });
    },
  });
}

export function useStartRecording() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (recordingId: string) => {
      const { data, error } = await client.POST(
        "/api/v1/recordings/{recording_id}/start",
        {
          params: { path: { recording_id: recordingId } },
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: (_, recordingId) => {
      // Invalidate specific recording and lists
      queryClient.invalidateQueries({
        queryKey: recordingKeys.detail(recordingId),
      });
      queryClient.invalidateQueries({ queryKey: recordingKeys.lists() });
    },
  });
}

export function useStopRecording() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (recordingId: string) => {
      const { data, error } = await client.POST(
        "/api/v1/recordings/{recording_id}/stop",
        {
          params: { path: { recording_id: recordingId } },
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: (_, recordingId) => {
      // Invalidate specific recording and lists
      queryClient.invalidateQueries({
        queryKey: recordingKeys.detail(recordingId),
      });
      queryClient.invalidateQueries({ queryKey: recordingKeys.lists() });
    },
  });
}

export function useCancelRecording() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (recordingId: string) => {
      const { data, error } = await client.DELETE(
        "/api/v1/recordings/{recording_id}",
        {
          params: { path: { recording_id: recordingId } },
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: (_, recordingId) => {
      // Invalidate specific recording and lists
      queryClient.invalidateQueries({
        queryKey: recordingKeys.detail(recordingId),
      });
      queryClient.invalidateQueries({ queryKey: recordingKeys.lists() });
    },
  });
}

export function usePostprocessRecording() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (recordingId: string) => {
      const { data, error } = await client.POST(
        "/api/v1/recordings/{recording_id}/postprocess",
        {
          params: { path: { recording_id: recordingId } },
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: (_, recordingId) => {
      // Invalidate specific recording and lists
      queryClient.invalidateQueries({
        queryKey: recordingKeys.detail(recordingId),
      });
      queryClient.invalidateQueries({ queryKey: recordingKeys.lists() });
    },
  });
}

export function useReprocessRecording() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      recordingId,
      language,
    }: {
      recordingId: string;
      language: string;
    }) => {
      const { data, error } = await client.POST(
        "/api/v1/recordings/{recording_id}/reprocess",
        {
          params: { path: { recording_id: recordingId } },
          body: { language },
        },
      );
      if (error) throw error;
      return data;
    },
    onSuccess: (_, { recordingId }) => {
      // Invalidate specific recording and lists
      queryClient.invalidateQueries({
        queryKey: recordingKeys.detail(recordingId),
      });
      queryClient.invalidateQueries({ queryKey: recordingKeys.lists() });
    },
  });
}

// Recording content queries
export function useRecordingTranscript(recordingId: string) {
  return useQuery({
    queryKey: [...recordingKeys.detail(recordingId), "transcript"] as const,
    queryFn: async () => {
      const { data, error } = await client.GET(
        "/api/v1/recordings/{recording_id}/transcript",
        {
          params: { path: { recording_id: recordingId } },
        },
      );
      if (error) throw error;
      return data;
    },
    enabled: !!recordingId,
  });
}

export function useRecordingSummary(recordingId: string) {
  return useQuery({
    queryKey: [...recordingKeys.detail(recordingId), "summary"] as const,
    queryFn: async () => {
      const { data, error } = await client.GET(
        "/api/v1/recordings/{recording_id}/summary",
        {
          params: { path: { recording_id: recordingId } },
        },
      );
      if (error) throw error;
      return data;
    },
    enabled: !!recordingId,
  });
}

// Extended hook for managing recordings as meetings
export interface UseRecordingsWithStatsResult {
  // Data
  recordings: RecordingResponse[];
  loading: boolean;
  error: Error | null;

  // Filtered views
  upcoming: RecordingResponse[];
  active: RecordingResponse[];
  completed: RecordingResponse[];

  // Stats
  stats: {
    total: number;
    upcoming: number;
    active: number;
    completed: number;
    success_rate: number;
  };

  // Actions
  startRecording: (recordingId: string) => Promise<void>;
  stopRecording: (recordingId: string) => Promise<void>;
  deleteRecording: (recordingId: string) => Promise<void>;
  postprocessRecording: (recordingId: string) => Promise<void>;
  startLoading: boolean;
  stopLoading: boolean;
  deleteLoading: boolean;
  postprocessLoading: boolean;
}

export function useRecordingsWithStats(): UseRecordingsWithStatsResult {
  const { data, isLoading, error } = useRecordings();
  const startRecordingMutation = useStartRecording();
  const stopRecordingMutation = useStopRecording();
  const cancelRecordingMutation = useCancelRecording();
  const postprocessRecordingMutation = usePostprocessRecording();

  const recordings = data || [];

  // Filter recordings by status
  const filtered = useMemo(() => {
    const upcoming = recordings.filter((r) => r.status === "scheduled");
    const active = recordings.filter((r) =>
      ["recording", "ready", "processing"].includes(r.status),
    );
    const completed = recordings.filter((r) =>
      ["completed", "error", "cancelled", "skipped"].includes(r.status),
    );

    return { upcoming, active, completed };
  }, [recordings]);

  // Calculate stats
  const stats = useMemo(() => {
    const total = recordings.length;
    const upcoming = filtered.upcoming.length;
    const active = filtered.active.length;
    const completed = filtered.completed.length;

    // Success rate calculation
    const finishedRecordings = recordings.filter((r) =>
      ["completed", "error", "cancelled", "skipped"].includes(r.status),
    );
    const successfulRecordings = finishedRecordings.filter(
      (r) => r.status === "completed",
    );
    const success_rate =
      finishedRecordings.length === 0
        ? 100
        : Math.round(
            (successfulRecordings.length / finishedRecordings.length) * 100,
          );

    return {
      total,
      upcoming,
      active,
      completed,
      success_rate,
    };
  }, [recordings, filtered]);

  // Start recording action
  const startRecording = async (recordingId: string) => {
    const recording = recordings.find((r) => r.id === recordingId);
    if (!recording || !["scheduled"].includes(recording.status)) {
      throw new Error("Cannot start this recording");
    }

    await startRecordingMutation.mutateAsync(recordingId);
  };

  // Stop recording action (graceful, with processing)
  const stopRecording = async (recordingId: string) => {
    const recording = recordings.find((r) => r.id === recordingId);
    if (!recording || !["recording"].includes(recording.status)) {
      throw new Error("Cannot stop this recording");
    }

    await stopRecordingMutation.mutateAsync(recordingId);
  };

  // Delete recording action (immediate, deletes artifacts)
  const deleteActiveRecording = async (recordingId: string) => {
    const recording = recordings.find((r) => r.id === recordingId);
    if (
      !recording ||
      !["recording", "ready", "processing"].includes(recording.status)
    ) {
      throw new Error("Cannot delete this recording");
    }

    await cancelRecordingMutation.mutateAsync(recordingId);
  };

  // Postprocess recording action (start postprocessing for ready recordings)
  const postprocessRecording = async (recordingId: string) => {
    const recording = recordings.find((r) => r.id === recordingId);
    if (!recording || recording.status !== "ready") {
      throw new Error("Cannot postprocess this recording");
    }

    await postprocessRecordingMutation.mutateAsync(recordingId);
  };

  // Delete recording action (deletes any recording regardless of status)
  const deleteRecording = async (recordingId: string) => {
    await cancelRecordingMutation.mutateAsync(recordingId);
  };

  return {
    recordings,
    loading: isLoading,
    error,

    upcoming: filtered.upcoming,
    active: filtered.active,
    completed: filtered.completed,

    stats,

    startRecording,
    stopRecording,
    deleteRecording,
    postprocessRecording,
    startLoading: startRecordingMutation.isPending,
    stopLoading: stopRecordingMutation.isPending,
    deleteLoading: cancelRecordingMutation.isPending,
    postprocessLoading: postprocessRecordingMutation.isPending,
  };
}
