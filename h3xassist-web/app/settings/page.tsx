"use client";

import { useState, useEffect } from "react";
import { client } from "@/src/lib/client";
import { parseAPIError } from "@/src/lib/errors";
import { cleanSettingsForUpdate } from "@/src/lib/settings-utils";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DynamicSectionCard } from "@/components/ui/dynamic-form";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Save, RefreshCw, RotateCcw } from "lucide-react";
import { toast } from "sonner";

interface JSONSchemaProperty {
  type: string;
  title?: string;
  description?: string;
  default?: any;
  properties?: { [key: string]: JSONSchemaProperty };
}

interface JSONSchema {
  type: string;
  properties: { [key: string]: JSONSchemaProperty };
  ui_metadata?: {
    sections: Array<{
      key: string;
      title: string;
      icon: string;
      description: string;
    }>;
  };
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<any>({});
  const [originalSettings, setOriginalSettings] = useState<any>({});
  const [schema, setSchema] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [restarting, setRestarting] = useState(false);

  useEffect(() => {
    loadSettingsAndSchema();
  }, []);

  const loadSettingsAndSchema = async () => {
    setLoading(true);
    try {
      const { data: settingsResponse, error: settingsError } =
        await client.GET("/api/v1/settings");
      if (settingsError) throw settingsError;

      const { data: schemaResponse, error: schemaError } = await client.GET(
        "/api/v1/settings/schema",
      );
      if (schemaError) throw schemaError;

      // Settings and schema are both dynamic - use the actual response types
      setSettings(settingsResponse);
      setOriginalSettings(structuredClone(settingsResponse));
      setSchema(schemaResponse);
      setHasChanges(false);
    } catch (error) {
      console.error("Failed to load settings:", error);
      toast.error(parseAPIError(error));
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    if (!originalSettings) {
      toast.error("No original settings to compare against");
      return;
    }

    setSaving(true);
    try {
      // Create update request with only changed sections
      const updateRequest: any = {};

      // Deep compare each top-level section
      for (const [section, currentValue] of Object.entries(settings)) {
        if (
          JSON.stringify(currentValue) !==
          JSON.stringify(originalSettings[section])
        ) {
          updateRequest[section] = currentValue;
        }
      }

      if (Object.keys(updateRequest).length === 0) {
        toast.info("No changes to save");
        return;
      }

      // Clean the settings before sending to API
      const cleanedRequest = cleanSettingsForUpdate(updateRequest);
      const { data: response, error } = await client.PUT("/api/v1/settings", {
        body: cleanedRequest,
      });
      if (error) throw error;

      // After saving, fetch updated settings from server without showing loading
      const { data: updatedSettings, error: settingsError } =
        await client.GET("/api/v1/settings");
      if (settingsError) throw settingsError;

      // Update local state with saved settings
      setSettings(updatedSettings);
      setOriginalSettings(structuredClone(updatedSettings));
      setHasChanges(false);

      toast.success("Settings saved successfully");
    } catch (error) {
      console.error("Failed to save settings:", error);
      toast.error(parseAPIError(error));
    } finally {
      setSaving(false);
    }
  };

  const restartService = async () => {
    setRestarting(true);
    try {
      const { data: response, error } = await client.POST(
        "/api/v1/service/restart",
      );
      if (error) throw error;

      toast.success("Service restart initiated successfully");
    } catch (error) {
      console.error("Failed to restart service:", error);
      toast.error(parseAPIError(error));
    } finally {
      setRestarting(false);
    }
  };

  const handleFieldChange = (path: string[], value: any) => {
    setSettings((prev: any) => {
      if (!prev) return prev;

      const newSettings = structuredClone(prev);
      let current = newSettings;

      // Navigate to the parent of the field
      for (let i = 0; i < path.length - 1; i++) {
        if (!current[path[i]]) {
          current[path[i]] = {};
        }
        current = current[path[i]];
      }

      // Set the field value
      current[path[path.length - 1]] = value;

      return newSettings;
    });
    setHasChanges(true);
  };

  if (loading || !schema || !settings) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex items-center gap-2">
          <RefreshCw className="h-4 w-4 animate-spin" />
          Loading settings...
        </div>
      </div>
    );
  }

  const sections = (schema?.ui_metadata?.sections || []) as Array<{
    key: string;
    title: string;
    icon: string;
    description: string;
  }>;

  return (
    <div className="flex-1 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
          <p className="text-muted-foreground">
            Configure H3xAssist behavior and integrations
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={loadSettingsAndSchema}
            disabled={loading}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Reload
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" disabled={restarting}>
                <RotateCcw className="mr-2 h-4 w-4" />
                {restarting ? "Restarting..." : "Restart Service"}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Restart Service</AlertDialogTitle>
                <AlertDialogDescription>
                  This will restart the H3xAssist service. Any active recordings
                  will be stopped gracefully. The service will automatically
                  reconnect after restart.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={restartService}
                  className="bg-red-600 hover:bg-red-700"
                >
                  <RotateCcw className="mr-2 h-4 w-4" />
                  Restart Service
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Button
            onClick={saveSettings}
            disabled={saving || !hasChanges}
            className={hasChanges ? "bg-orange-600 hover:bg-orange-700" : ""}
          >
            <Save className="mr-2 h-4 w-4" />
            {saving
              ? "Saving..."
              : hasChanges
                ? "Save Changes *"
                : "No Changes"}
          </Button>
        </div>
      </div>

      {/* Dynamic Settings Tabs */}
      <Tabs defaultValue={sections[0]?.key} className="space-y-4">
        <TabsList
          className="grid w-full"
          style={{ gridTemplateColumns: `repeat(${sections.length}, 1fr)` }}
        >
          {sections.map((section) => (
            <TabsTrigger key={section.key} value={section.key}>
              {section.title}
            </TabsTrigger>
          ))}
        </TabsList>

        {sections.map((section) => (
          <TabsContent key={section.key} value={section.key}>
            <DynamicSectionCard
              schema={schema}
              data={settings}
              onChange={handleFieldChange}
              sectionKey={section.key}
              title={section.title}
              description={section.description}
              icon={section.icon}
            />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
