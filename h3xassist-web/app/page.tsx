"use client";

import { useRecordingsWithStats } from "@/src/hooks/useRecordings";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Calendar, Video, CheckCircle, Clock } from "lucide-react";
import { UpcomingEvents } from "@/components/dashboard-columns/upcoming-events";
import { ActiveSessions } from "@/components/dashboard-columns/active-sessions";
import { CompletedItems } from "@/components/dashboard-columns/completed-items";
import { CreateRecordingDialog } from "@/components/create-recording-dialog";

export default function OverviewPage() {
  const {
    recordings,
    upcoming,
    active,
    completed,
    startRecording,
    stopRecording,
    deleteRecording,
    postprocessRecording,
    startLoading,
    stopLoading,
    deleteLoading,
    postprocessLoading,
  } = useRecordingsWithStats();

  // Calculate stats from recordings
  const completedToday = completed.filter((r) => {
    const recordingDate = new Date(r.actual_start || r.scheduled_start);
    const today = new Date();
    return recordingDate.toDateString() === today.toDateString();
  }).length;

  const totalRecordings = recordings.length;

  // Start recording handler
  const handleStartRecording = async (recordingId: string) => {
    try {
      await startRecording(recordingId);
      toast.success("Recording started successfully");
    } catch (error) {
      console.error("Failed to start recording:", error);
      toast.error("Failed to start recording");
    }
  };

  // Postprocess recording handler
  const handlePostprocessRecording = async (recordingId: string) => {
    try {
      await postprocessRecording(recordingId);
      toast.success("Recording added to postprocessing queue");
    } catch (error) {
      console.error("Failed to start postprocessing:", error);
      toast.error("Failed to start postprocessing");
    }
  };

  // Delete recording handler
  const handleDeleteRecording = async (recordingId: string) => {
    try {
      await deleteRecording(recordingId);
      toast.success("Recording deleted successfully");
    } catch (error) {
      console.error("Failed to delete recording:", error);
      toast.error("Failed to delete recording");
    }
  };

  // Completed items handlers
  const handleViewDetails = (recordingId: string) => {
    // Navigate to recordings page with specific recording, indicating we came from overview
    window.location.href = `/recordings?id=${recordingId}&from=overview`;
  };

  return (
    <div className="flex-1 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
            Overview
          </h1>
          <p className="text-sm sm:text-base text-muted-foreground">
            Monitor your recordings and scheduled meetings
          </p>
        </div>
        <CreateRecordingDialog />
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Scheduled Recordings
            </CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{upcoming.length}</div>
            <p className="text-xs text-muted-foreground">Waiting to record</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Active Sessions
            </CardTitle>
            <Video className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{active.length}</div>
            <p className="text-xs text-muted-foreground">Currently recording</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Completed Today
            </CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{completedToday}</div>
            <p className="text-xs text-muted-foreground">Finished meetings</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total Recordings
            </CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalRecordings}</div>
            <p className="text-xs text-muted-foreground">All time</p>
          </CardContent>
        </Card>
      </div>

      {/* Dashboard Columns */}
      <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
        <UpcomingEvents
          recordings={upcoming}
          onStartRecording={handleStartRecording}
          onDeleteRecording={handleDeleteRecording}
          startLoading={startLoading}
          deleteLoading={deleteLoading}
        />
        <ActiveSessions
          recordings={active}
          onStopRecording={stopRecording}
          onDeleteRecording={deleteRecording}
          onPostprocessRecording={handlePostprocessRecording}
          stopLoading={stopLoading}
          deleteLoading={deleteLoading}
          postprocessLoading={postprocessLoading}
        />
        <CompletedItems
          recordings={completed}
          onViewDetails={handleViewDetails}
          onDeleteRecording={handleDeleteRecording}
          deleteLoading={deleteLoading}
        />
      </div>
    </div>
  );
}
