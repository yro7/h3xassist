"use client";

import { useState, useEffect } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DateTimePicker } from "@/components/ui/date-time-picker";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useProfiles } from "@/src/contexts/profiles-context";
import { useCreateRecording } from "@/src/hooks/useRecordings";
import { toast } from "sonner";
import { LanguageSelect } from "./language-select";

interface CreateRecordingDialogProps {
  trigger?: React.ReactNode;
  onSuccess?: () => void;
}

export function CreateRecordingDialog({
  trigger,
  onSuccess,
}: CreateRecordingDialogProps) {
  const [open, setOpen] = useState(false);
  const { profiles } = useProfiles();
  const createRecordingMutation = useCreateRecording();

  const [formData, setFormData] = useState({
    subject: "",
    url: "",
    scheduled_start: undefined as Date | undefined,
    scheduled_end: undefined as Date | undefined,
    language: null as string | null,
    profile: "default",
    use_school_meet: false,
  });

  // Set default times when dialog opens
  useEffect(() => {
    if (open) {
      const now = new Date();
      // Round to next 5-minute interval
      const roundedNow = new Date(now);
      roundedNow.setMinutes(Math.ceil(now.getMinutes() / 5) * 5, 0, 0);

      const oneHourLater = new Date(roundedNow.getTime() + 60 * 60 * 1000);

      setFormData((prev) => ({
        ...prev,
        scheduled_start: roundedNow,
        scheduled_end: oneHourLater,
      }));
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.scheduled_start || !formData.scheduled_end) {
      toast.error("Please select start and end times");
      return;
    }

    try {
      await createRecordingMutation.mutateAsync({
        subject: formData.subject,
        url: formData.url,
        scheduled_start: formData.scheduled_start.toISOString(),
        scheduled_end: formData.scheduled_end.toISOString(),
        language: formData.language || undefined,
        profile: formData.profile,
        use_school_meet: formData.use_school_meet,
      });

      toast.success("Recording created successfully");
      setOpen(false);

      // Reset form
      const now = new Date();
      const roundedNow = new Date(now);
      roundedNow.setMinutes(Math.ceil(now.getMinutes() / 5) * 5, 0, 0);
      const oneHourLater = new Date(roundedNow.getTime() + 60 * 60 * 1000);

      setFormData({
        subject: "",
        url: "",
        scheduled_start: roundedNow,
        scheduled_end: oneHourLater,
        language: null,
        profile: "default",
        use_school_meet: false,
      });

      onSuccess?.();
    } catch (error) {
      console.error("Failed to create recording:", error);
      toast.error("Failed to create recording");
    }
  };

  // Auto-fill end time when start time changes (default 1 hour duration)
  const handleStartTimeChange = (date: Date | undefined) => {
    setFormData((prev) => {
      const newData = { ...prev, scheduled_start: date };

      if (date && !prev.scheduled_end) {
        const endDate = new Date(date.getTime() + 60 * 60 * 1000); // +1 hour
        newData.scheduled_end = endDate;
      }

      return newData;
    });
  };

  const defaultTrigger = (
    <Button>
      <Plus className="mr-2 h-4 w-4" />
      Create Recording
    </Button>
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger || defaultTrigger}</DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto p-6">
        <DialogHeader>
          <DialogTitle>Create New Recording</DialogTitle>
          <DialogDescription>
            Schedule a new meeting recording. The recording will start
            automatically at the scheduled time.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 mt-4">
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="subject">Subject *</Label>
              <Input
                id="subject"
                value={formData.subject}
                onChange={(e) =>
                  setFormData({ ...formData, subject: e.target.value })
                }
                placeholder="Meeting topic or title"
                required
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="url">Meeting URL *</Label>
              <Input
                id="url"
                type="url"
                value={formData.url}
                onChange={(e) =>
                  setFormData({ ...formData, url: e.target.value })
                }
                placeholder="https://meet.google.com/xxx-xxxx-xxx"
                required
              />
            </div>

            <div className="space-y-4">
              <div className="grid gap-2">
                <Label>Start Time *</Label>
                <DateTimePicker
                  value={formData.scheduled_start}
                  onChange={handleStartTimeChange}
                  placeholder="Select start time"
                />
              </div>

              <div className="grid gap-2">
                <Label>End Time *</Label>
                <DateTimePicker
                  value={formData.scheduled_end}
                  onChange={(date) =>
                    setFormData({ ...formData, scheduled_end: date })
                  }
                  placeholder="Select end time"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="profile">Browser Profile</Label>
                <Select
                  value={formData.profile}
                  onValueChange={(value) =>
                    setFormData({ ...formData, profile: value })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select profile" />
                  </SelectTrigger>
                  <SelectContent>
                    {profiles.map((profile) => (
                      <SelectItem key={profile.name} value={profile.name}>
                        {profile.name === "default" ? "Default" : profile.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="language">Language</Label>
                <LanguageSelect
                  value={formData.language}
                  onValueChange={(value) =>
                    setFormData({ ...formData, language: value || null })
                  }
                  placeholder="Auto-detect"
                />
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <input
                id="school-meet"
                type="checkbox"
                checked={formData.use_school_meet}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    use_school_meet: e.target.checked,
                  })
                }
                className="rounded border border-input"
              />
              <Label htmlFor="school-meet" className="text-sm">
                Use School Google Meet mode
              </Label>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createRecordingMutation.isPending}>
              {createRecordingMutation.isPending
                ? "Creating..."
                : "Create Recording"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
