"use client";

import { useState, useEffect } from "react";
import { Circle } from "lucide-react";

interface RecordingIndicatorProps {
  startTime: string;
  variant?: "default" | "white";
}

export function RecordingIndicator({
  startTime,
  variant = "default",
}: RecordingIndicatorProps) {
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

  if (variant === "white") {
    return <span className="text-xs font-mono text-red-100">{duration}</span>;
  }

  return (
    <div className="flex items-center gap-2">
      <div className="relative flex items-center">
        <Circle className="w-2 h-2 fill-red-500 text-red-500" />
        <div className="absolute inset-0 w-2 h-2 rounded-full bg-red-500 animate-ping" />
      </div>
      <span className="text-xs font-medium">Recording</span>
      <span className="text-xs text-muted-foreground font-mono">
        {duration}
      </span>
    </div>
  );
}
