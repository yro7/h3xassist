"use client";

import { CheckCircle, Eye, Trash2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeleteConfirmationDialog } from "@/components/delete-confirmation-dialog";
import type { RecordingResponse } from "@/src/types/helpers";
import { formatDateTime, formatFileSize } from "@/src/lib/date-format";

interface CompletedItemsProps {
  recordings: RecordingResponse[];
  onViewDetails?: (recordingId: string) => void;
  onDeleteRecording?: (recordingId: string) => void;
  deleteLoading?: boolean;
}

export function CompletedItems({
  recordings,
  onViewDetails,
  onDeleteRecording,
  deleteLoading,
}: CompletedItemsProps) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-green-600">
          <CheckCircle className="h-5 w-5" />
          Completed ({recordings.length})
        </CardTitle>
        <CardDescription>Finished recordings</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {recordings.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <CheckCircle className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">No completed recordings</p>
            <p className="text-sm">Completed recordings will appear here</p>
          </div>
        ) : (
          recordings.slice(0, 8).map((recording) => (
            <div
              key={recording.id}
              className="flex items-start justify-between p-3 rounded-lg border bg-card/50 hover:bg-card transition-colors"
            >
              <div className="flex-1 space-y-2">
                <div className="flex items-center gap-2">
                  <div
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      recording.status === "completed"
                        ? "bg-green-500"
                        : recording.status === "error"
                          ? "bg-red-500"
                          : "bg-gray-400"
                    }`}
                  />
                  <h4 className="font-medium leading-none">
                    {recording.subject}
                  </h4>
                </div>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span>
                    {formatDateTime(
                      recording.actual_start || recording.scheduled_start,
                    )}
                  </span>
                  {recording.duration_sec && (
                    <span>{Math.round(recording.duration_sec / 60)}min</span>
                  )}
                  {recording.bytes_written && recording.bytes_written > 0 && (
                    <span>{formatFileSize(recording.bytes_written)}</span>
                  )}
                </div>
                {recording.error_message && (
                  <p className="text-xs text-red-600 truncate">
                    {recording.error_message}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-1 ml-2">
                {recording.status === "completed" && onViewDetails && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onViewDetails(recording.id)}
                  >
                    <Eye className="mr-1 h-3 w-3" />
                    View
                  </Button>
                )}
                {recording.status === "error" && onDeleteRecording && (
                  <DeleteConfirmationDialog
                    title="Delete Recording"
                    description="Are you sure you want to delete this recording? This action cannot be undone."
                    onConfirm={() => onDeleteRecording(recording.id)}
                    loading={deleteLoading}
                    trigger={
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-red-600"
                        title="Delete recording"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    }
                  />
                )}
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
