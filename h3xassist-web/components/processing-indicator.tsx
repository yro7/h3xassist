"use client";

import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";

interface ProcessingIndicatorProps {
  stage?: string;
  startTime?: string;
}

const STAGE_CONFIG = {
  asr: {
    label: "Transcribing",
    description: "Converting speech to text",
  },
  mapping: {
    label: "Diarization",
    description: "Identifying speakers",
  },
  summary: {
    label: "Summarizing",
    description: "Generating AI summary",
  },
  export: {
    label: "Finalizing",
    description: "Preparing files",
  },
  default: {
    label: "Processing",
    description: "Working...",
  },
};

function ProcessingTimer({ startTime }: { startTime: string }) {
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    const updateTimer = () => {
      const start = new Date(startTime);
      const now = new Date();
      const diffMs = Math.max(0, now.getTime() - start.getTime());
      setDuration(Math.floor(diffMs / 1000));
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  const minutes = Math.floor(duration / 60);
  const seconds = duration % 60;

  return (
    <span className="text-xs font-mono">
      {minutes}:{seconds.toString().padStart(2, "0")}
    </span>
  );
}

export function ProcessingIndicator({
  stage = "default",
  startTime,
}: ProcessingIndicatorProps) {
  const config =
    STAGE_CONFIG[stage as keyof typeof STAGE_CONFIG] || STAGE_CONFIG.default;

  return (
    <div className="flex items-center gap-2">
      <div className="flex flex-col items-end text-right">
        <span className="text-xs font-medium">{config.label}</span>
        {startTime && (
          <span className="text-xs text-muted-foreground font-mono">
            <ProcessingTimer startTime={startTime} />
          </span>
        )}
      </div>

      <div className="relative">
        <Loader2 className="w-4 h-4 text-muted-foreground animate-spin" />
      </div>
    </div>
  );
}
