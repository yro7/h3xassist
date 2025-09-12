"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const LANGUAGE_OPTIONS = [
  { value: "auto", label: "Auto-detect" },
  { value: "uk", label: "Ukrainian" },
  { value: "en", label: "English" },
  { value: "de", label: "German" },
  { value: "fr", label: "French" },
  { value: "es", label: "Spanish" },
  { value: "it", label: "Italian" },
  { value: "pl", label: "Polish" },
  { value: "ru", label: "Russian" },
] as const;

interface LanguageSelectProps {
  value?: string | null;
  onValueChange?: (value: string) => void;
  placeholder?: string;
}

export function LanguageSelect({
  value,
  onValueChange,
  placeholder = "Select language...",
}: LanguageSelectProps) {
  const selectedValue = value || "auto";

  const handleValueChange = (newValue: string) => {
    // Convert "auto" back to null for the API
    const apiValue = newValue === "auto" ? null : newValue;
    onValueChange?.(apiValue as string);
  };

  return (
    <Select value={selectedValue} onValueChange={handleValueChange}>
      <SelectTrigger>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {LANGUAGE_OPTIONS.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
