"use client";

import { useState, useEffect } from "react";
import { Clock, Calendar, X, Plus, PlayCircle } from "lucide-react";
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
import { formatDateTime } from "@/src/lib/date-format";

interface UpcomingEventsProps {
  recordings: RecordingResponse[];
  onDeleteRecording: (recordingId: string) => void;
  onStartRecording: (recordingId: string) => void;
  deleteLoading: boolean;
  startLoading: boolean;
}

function CountdownTimer({ startTime }: { startTime: string }) {
  const [timeUntil, setTimeUntil] = useState("");

  useEffect(() => {
    const updateCountdown = () => {
      const now = new Date();
      const start = new Date(startTime);
      const diffMs = start.getTime() - now.getTime();

      if (diffMs < 0) {
        setTimeUntil("Overdue");
        return;
      }

      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
      const diffSeconds = Math.floor((diffMs % (1000 * 60)) / 1000);

      if (diffHours === 0 && diffMinutes < 60) {
        // Show minutes and seconds when less than 1 hour
        setTimeUntil(`in ${diffMinutes}m ${diffSeconds}s`);
      } else if (diffHours < 24) {
        setTimeUntil(`in ${diffHours}h ${diffMinutes}m`);
      } else {
        const diffDays = Math.floor(diffHours / 24);
        setTimeUntil(`in ${diffDays}d ${diffHours % 24}h`);
      }
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  return (
    <Badge variant="secondary" className="text-xs font-mono">
      {timeUntil}
    </Badge>
  );
}

export function UpcomingEvents({
  recordings,
  onDeleteRecording,
  onStartRecording,
  deleteLoading,
  startLoading,
}: UpcomingEventsProps) {
  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-blue-600">
          <Calendar className="h-5 w-5" />
          Upcoming ({recordings.length})
        </CardTitle>
        <CardDescription>Scheduled recordings</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {recordings.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Calendar className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">No scheduled recordings</p>
            <p className="text-sm">
              Recordings will appear here when scheduled
            </p>
          </div>
        ) : (
          recordings.slice(0, 8).map((recording) => (
            <div
              key={recording.id}
              className="flex items-start justify-between p-3 rounded-lg border bg-card/50 hover:bg-card transition-colors"
            >
              <div className="flex-1 space-y-2">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0" />
                  <h4 className="font-medium leading-none">
                    {recording.subject}
                  </h4>
                  <Badge variant="outline" className="text-xs">
                    {recording.source}
                  </Badge>
                </div>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <div className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    <span>{formatDateTime(recording.scheduled_start)}</span>
                  </div>
                  <CountdownTimer startTime={recording.scheduled_start} />
                </div>
              </div>
              <div className="flex items-center gap-1 ml-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => onStartRecording(recording.id)}
                  disabled={startLoading}
                  className="h-6 w-6 text-muted-foreground hover:text-green-600"
                  title="Start recording"
                >
                  <PlayCircle className="h-3 w-3" />
                </Button>
                <DeleteConfirmationDialog
                  title="Delete Recording"
                  description="Are you sure you want to delete this scheduled recording? This action cannot be undone."
                  onConfirm={() => onDeleteRecording(recording.id)}
                  loading={deleteLoading}
                  trigger={
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 text-muted-foreground hover:text-red-600"
                      title="Delete recording"
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  }
                />
              </div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}
