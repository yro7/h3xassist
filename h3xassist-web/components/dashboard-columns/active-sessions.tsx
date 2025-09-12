"use client";
import { useState, useEffect } from "react";
import { Activity, Square, X, Cog } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DeleteConfirmationDialog } from "@/components/delete-confirmation-dialog";
import type { RecordingResponse } from "@/src/types/helpers";

interface ActiveSessionsProps {
  recordings: RecordingResponse[];
  onStopRecording?: (recordingId: string) => void;
  onDeleteRecording?: (recordingId: string) => void;
  onPostprocessRecording?: (recordingId: string) => void;
  stopLoading?: boolean;
  deleteLoading?: boolean;
  postprocessLoading?: boolean;
}

function SimpleTimer({ startTime }: { startTime: string }) {
  const [duration, setDuration] = useState("");

  useEffect(() => {
    const updateTimer = () => {
      const start = new Date(startTime);
      const now = new Date();
      const diffMs = now.getTime() - start.getTime();

      if (diffMs < 0) {
        setDuration("0:00");
        return;
      }

      const diffMinutes = Math.floor(diffMs / (1000 * 60));
      const diffSeconds = Math.floor((diffMs % (1000 * 60)) / 1000);

      const minutes = Math.floor(diffMinutes % 60);
      const hours = Math.floor(diffMinutes / 60);

      if (hours > 0) {
        setDuration(
          `${hours}:${minutes.toString().padStart(2, "0")}:${diffSeconds.toString().padStart(2, "0")}`,
        );
      } else {
        setDuration(`${minutes}:${diffSeconds.toString().padStart(2, "0")}`);
      }
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  return (
    <span className="text-xs text-muted-foreground font-mono">{duration}</span>
  );
}

function getStatusDisplay(
  status: string,
  stage?: string | null,
): { text: string; color: string; icon: string } {
  switch (status) {
    case "recording":
      return { text: "Recording", color: "text-red-600", icon: "bg-red-500" };
    case "processing":
      const stageConfig = {
        asr: "Transcribing",
        mapping: "Diarization",
        summary: "Summarizing",
        export: "Finalizing",
      } as const;
      const stageText = stage
        ? stageConfig[stage as keyof typeof stageConfig] || "Processing"
        : "Processing";
      return {
        text: stageText,
        color: "text-yellow-600",
        icon: "bg-yellow-500",
      };
    case "ready":
      return {
        text: "Waiting for processing",
        color: "text-blue-600",
        icon: "bg-blue-500",
      };
    default:
      return { text: status, color: "text-gray-600", icon: "bg-gray-500" };
  }
}

export function ActiveSessions({
  recordings,
  onStopRecording,
  onDeleteRecording,
  onPostprocessRecording,
  stopLoading,
  deleteLoading,
  postprocessLoading,
}: ActiveSessionsProps) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-red-600">
          <Activity className="h-5 w-5" />
          Active ({recordings.length})
        </CardTitle>
        <CardDescription>Currently working</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {recordings.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Activity className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">No active recordings</p>
            <p className="text-sm">Active recordings will appear here</p>
          </div>
        ) : (
          [...recordings]
            .sort((a, b) => {
              const statusPriority = {
                recording: 0,
                processing: 1,
                ready: 2,
              } as const;
              const priorityA =
                statusPriority[a.status as keyof typeof statusPriority] ?? 3;
              const priorityB =
                statusPriority[b.status as keyof typeof statusPriority] ?? 3;
              return priorityA - priorityB;
            })
            .slice(0, 8)
            .map((recording) => (
              <div
                key={recording.id}
                className={`relative overflow-hidden rounded-lg border border-border bg-card hover:bg-accent/50 p-4 transition-all duration-200 ${
                  recording.status === "recording"
                    ? "shadow-lg border-l-4 border-l-red-500"
                    : recording.status === "processing"
                      ? "shadow-md border-l-4 border-l-yellow-500"
                      : "shadow-sm border-l-4 border-l-blue-500"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <div
                        className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                          getStatusDisplay(
                            recording.status,
                            recording.postprocess_stage,
                          ).icon
                        } ${
                          recording.status === "recording"
                            ? "animate-pulse"
                            : ""
                        }`}
                      />
                      <h4 className="font-semibold text-foreground">
                        {recording.subject}
                      </h4>
                    </div>

                    <div className="flex items-center gap-2">
                      <span
                        className={`text-sm font-medium ${
                          getStatusDisplay(
                            recording.status,
                            recording.postprocess_stage,
                          ).color
                        }`}
                      >
                        {
                          getStatusDisplay(
                            recording.status,
                            recording.postprocess_stage,
                          ).text
                        }
                      </span>

                      {recording.status === "recording" &&
                        typeof recording.actual_start === "string" && (
                          <>
                            <div className="text-xs text-muted-foreground">
                              •
                            </div>
                            <SimpleTimer startTime={recording.actual_start} />
                          </>
                        )}

                      {recording.status === "processing" && (
                        <>
                          <div className="text-xs text-muted-foreground">•</div>
                          <SimpleTimer
                            startTime={
                              (recording.actual_end ??
                                recording.actual_start ??
                                recording.scheduled_start) as string
                            }
                          />
                        </>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-1 ml-2">
                    {recording.status === "recording" && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onStopRecording?.(recording.id)}
                        disabled={stopLoading}
                        className="h-8 w-8 text-muted-foreground hover:text-orange-600"
                        title="Stop recording"
                      >
                        <Square className="h-4 w-4" />
                      </Button>
                    )}

                    {recording.status === "ready" && onPostprocessRecording && (
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onPostprocessRecording(recording.id)}
                        disabled={postprocessLoading}
                        className="h-8 w-8 text-muted-foreground hover:text-blue-600"
                        title="Start postprocessing"
                      >
                        <Cog className="h-4 w-4" />
                      </Button>
                    )}

                    <DeleteConfirmationDialog
                      title="Delete Recording"
                      description="Are you sure you want to delete this recording? This will immediately stop recording and delete all files."
                      onConfirm={() => onDeleteRecording?.(recording.id)}
                      loading={deleteLoading}
                      trigger={
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-red-600"
                          title="Delete recording"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      }
                    />
                  </div>
                </div>
              </div>
            ))
        )}
      </CardContent>
    </Card>
  );
}
