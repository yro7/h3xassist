/**
 * Settings preprocessing utilities
 */

/**
 * Recursively converts empty strings to null/undefined for proper API handling
 * This ensures optional fields with empty strings are sent as null instead
 */
export function preprocessSettingsForAPI(obj: any): any {
  if (obj === null || obj === undefined) {
    return obj;
  }

  // Handle empty strings - convert to null for optional fields
  if (typeof obj === "string" && obj === "") {
    return null;
  }

  // Handle arrays
  if (Array.isArray(obj)) {
    return obj.map((item) => preprocessSettingsForAPI(item));
  }

  // Handle objects
  if (typeof obj === "object") {
    const processed: any = {};
    for (const [key, value] of Object.entries(obj)) {
      // Special handling for numeric fields that can be optional
      if (isOptionalNumericField(key) && value === "") {
        processed[key] = null;
      } else {
        processed[key] = preprocessSettingsForAPI(value);
      }
    }
    return processed;
  }

  return obj;
}

/**
 * List of field names that are optional numeric fields
 * These should be converted to null when empty
 */
function isOptionalNumericField(fieldName: string): boolean {
  const optionalNumericFields = [
    "max_output_tokens",
    "window_start_sec",
    "window_end_sec",
    "max_duration_sec",
    // Add more optional numeric fields as needed
  ];

  return optionalNumericFields.includes(fieldName);
}

/**
 * Clean settings object before sending to API
 * Removes undefined values and converts empty strings appropriately
 */
export function cleanSettingsForUpdate(settings: any): any {
  const cleaned = preprocessSettingsForAPI(settings);

  // Remove any undefined values (but keep null values)
  function removeUndefined(obj: any): any {
    if (obj === undefined) return null;
    if (obj === null) return null;
    if (Array.isArray(obj)) return obj.map(removeUndefined);
    if (typeof obj !== "object") return obj;

    const result: any = {};
    for (const [key, value] of Object.entries(obj)) {
      if (value !== undefined) {
        result[key] = removeUndefined(value);
      }
    }
    return result;
  }

  return removeUndefined(cleaned);
}
