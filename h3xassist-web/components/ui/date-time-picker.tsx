"use client";

import * as React from "react";
import { useRef, useEffect } from "react";
import { format } from "date-fns";
import { Calendar as CalendarIcon, Clock } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";

interface DateTimePickerProps {
  value?: Date;
  onChange?: (date: Date | undefined) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function DateTimePicker({
  value,
  onChange,
  placeholder = "Pick a date and time",
  disabled = false,
}: DateTimePickerProps) {
  const [date, setDate] = React.useState<Date | undefined>(value);
  const [hour, setHour] = React.useState<string>(
    value ? format(value, "HH") : "09",
  );
  const [minute, setMinute] = React.useState<string>(
    value ? format(value, "mm") : "00",
  );

  React.useEffect(() => {
    setDate(value);
    if (value) {
      setHour(format(value, "HH"));
      setMinute(format(value, "mm"));
    }
  }, [value]);

  const handleDateChange = (selectedDate: Date | undefined) => {
    if (selectedDate) {
      selectedDate.setHours(parseInt(hour), parseInt(minute));
      setDate(selectedDate);
      onChange?.(selectedDate);
    } else {
      setDate(undefined);
      onChange?.(undefined);
    }
  };

  const handleTimeChange = (newHour: string, newMinute: string) => {
    setHour(newHour);
    setMinute(newMinute);
    if (date) {
      const newDateTime = new Date(date);
      newDateTime.setHours(parseInt(newHour), parseInt(newMinute));
      setDate(newDateTime);
      onChange?.(newDateTime);
    }
  };

  // Generate hours array (00-23)
  const hours = Array.from({ length: 24 }, (_, i) =>
    i.toString().padStart(2, "0"),
  );

  // Generate minutes array (00-59, step 5)
  const minutes = Array.from({ length: 12 }, (_, i) =>
    (i * 5).toString().padStart(2, "0"),
  );

  return (
    <div className="flex gap-2">
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant={"outline"}
            className={cn(
              "justify-start text-left font-normal flex-1",
              !date && "text-muted-foreground",
            )}
            disabled={disabled}
          >
            <CalendarIcon className="mr-2 h-4 w-4" />
            {date ? format(date, "dd/MM/yyyy") : <span>Select date</span>}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            selected={date}
            onSelect={handleDateChange}
            initialFocus
          />
        </PopoverContent>
      </Popover>

      <Popover modal>
        <PopoverTrigger asChild>
          <Button
            variant={"outline"}
            className={cn(
              "justify-start text-left font-normal w-[120px]",
              !date && "text-muted-foreground",
            )}
            disabled={disabled}
          >
            <Clock className="mr-2 h-4 w-4" />
            {date ? `${hour}:${minute}` : "00:00"}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[200px] p-2" align="start" sideOffset={5}>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="text-xs font-medium mb-1">Hour</div>
              <ScrollArea className="h-[200px]">
                <div className="pr-2">
                  {hours.map((h) => (
                    <Button
                      key={h}
                      variant={hour === h ? "default" : "ghost"}
                      className="w-full justify-center mb-1"
                      size="sm"
                      onClick={() => handleTimeChange(h, minute)}
                    >
                      {h}
                    </Button>
                  ))}
                </div>
              </ScrollArea>
            </div>
            <div>
              <div className="text-xs font-medium mb-1">Minute</div>
              <ScrollArea className="h-[200px]">
                <div className="pr-2">
                  {minutes.map((m) => (
                    <Button
                      key={m}
                      variant={minute === m ? "default" : "ghost"}
                      className="w-full justify-center mb-1"
                      size="sm"
                      onClick={() => handleTimeChange(hour, m)}
                    >
                      {m}
                    </Button>
                  ))}
                </div>
              </ScrollArea>
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
