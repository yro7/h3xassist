"use client";

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import { client } from "../lib/client";
import { parseAPIError } from "../lib/errors";
import type { BrowserProfile } from "../types/helpers";

interface ProfilesContextType {
  profiles: BrowserProfile[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

const ProfilesContext = createContext<ProfilesContextType | undefined>(
  undefined,
);

export function ProfilesProvider({ children }: { children: React.ReactNode }) {
  const [profiles, setProfiles] = useState<BrowserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProfiles = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const { data, error } = await client.GET("/api/v1/profiles");
      if (error) throw error;
      setProfiles(data);
    } catch (err) {
      const errorMessage = parseAPIError(err);
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  const value = {
    profiles,
    loading,
    error,
    refetch: fetchProfiles,
  };

  return (
    <ProfilesContext.Provider value={value}>
      {children}
    </ProfilesContext.Provider>
  );
}

export function useProfiles() {
  const context = useContext(ProfilesContext);
  if (context === undefined) {
    throw new Error("useProfiles must be used within a ProfilesProvider");
  }
  return context;
}
