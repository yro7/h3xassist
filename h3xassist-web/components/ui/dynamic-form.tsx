"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import * as Icons from "lucide-react";

interface JSONSchemaProperty {
  type: string;
  title?: string;
  description?: string;
  default?: any;
  enum?: string[];
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  properties?: { [key: string]: JSONSchemaProperty };
  required?: string[];
  format?: string;
}

interface JSONSchema {
  type: string;
  properties: { [key: string]: JSONSchemaProperty };
  required?: string[];
  ui_metadata?: {
    sections: Array<{
      key: string;
      title: string;
      icon: string;
      description: string;
    }>;
  };
}

interface DynamicFormProps {
  schema: JSONSchema;
  data: any;
  onChange: (path: string[], value: any) => void;
  sectionKey?: string;
}

export function DynamicForm({
  schema,
  data,
  onChange,
  sectionKey,
}: DynamicFormProps) {
  const renderField = (
    key: string,
    property: JSONSchemaProperty,
    value: any,
    path: string[] = [],
  ) => {
    const fieldPath = [...path, key];
    const fieldId = fieldPath.join(".");
    const isRequired = schema.required?.includes(key) || false;

    const handleChange = (newValue: any) => {
      onChange(fieldPath, newValue);
    };

    // Handle anyOf (Optional fields in Pydantic)
    if ((property as any).anyOf) {
      const anyOfOptions = (property as any).anyOf;
      // Find the non-null type
      const nonNullOption = anyOfOptions.find(
        (option: any) => option.type !== "null",
      );
      if (nonNullOption) {
        // If it's a $ref, resolve it
        if (nonNullOption.$ref) {
          const resolvedDef = resolveRef(nonNullOption.$ref, schema);
          property = { ...property, ...resolvedDef };
        } else {
          // Use the non-null option as the base property
          property = { ...property, ...nonNullOption };
        }
      }
    }

    // Handle direct $ref without anyOf (nested objects)
    if ((property as any).$ref && !property.type) {
      const resolvedDef = resolveRef((property as any).$ref, schema);
      if (resolvedDef) {
        property = { ...property, ...resolvedDef };
      }
    }

    // Handle nested objects
    if (property.type === "object" && property.properties) {
      return (
        <div key={key} className="space-y-4">
          <div className="border-l-2 border-muted pl-4">
            <h4 className="font-medium text-sm mb-2">
              {property.title || key}
            </h4>
            {property.description && (
              <p className="text-xs text-muted-foreground mb-3">
                {property.description}
              </p>
            )}
            <div className="space-y-3">
              {Object.entries(property.properties).map(
                ([nestedKey, nestedProp]) =>
                  renderField(
                    nestedKey,
                    nestedProp,
                    value?.[nestedKey],
                    fieldPath,
                  ),
              )}
            </div>
          </div>
        </div>
      );
    }

    // Boolean fields (Switch)
    if (property.type === "boolean") {
      return (
        <div key={key} className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label
              htmlFor={fieldId}
              className={isRequired ? "text-red-500" : ""}
            >
              {property.title || key}
              {isRequired && " *"}
            </Label>
            {property.description && (
              <p className="text-sm text-muted-foreground">
                {property.description}
              </p>
            )}
          </div>
          <Switch
            id={fieldId}
            checked={value ?? property.default ?? false}
            onCheckedChange={handleChange}
          />
        </div>
      );
    }

    // Enum fields (Select)
    if (property.enum && property.enum.length > 0) {
      return (
        <div key={key} className="grid gap-2">
          <Label htmlFor={fieldId} className={isRequired ? "text-red-500" : ""}>
            {property.title || key}
            {isRequired && " *"}
          </Label>
          <Select
            value={value ?? property.default ?? ""}
            onValueChange={handleChange}
          >
            <SelectTrigger>
              <SelectValue placeholder={`Select ${property.title || key}`} />
            </SelectTrigger>
            <SelectContent>
              {property.enum.map((option) => (
                <SelectItem key={option} value={option}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {property.description && (
            <p className="text-xs text-muted-foreground">
              {property.description}
            </p>
          )}
        </div>
      );
    }

    // Number fields
    if (property.type === "number" || property.type === "integer") {
      return (
        <div key={key} className="grid gap-2">
          <Label htmlFor={fieldId} className={isRequired ? "text-red-500" : ""}>
            {property.title || key}
            {isRequired && " *"}
          </Label>
          <Input
            id={fieldId}
            type="number"
            value={value ?? property.default ?? ""}
            onChange={(e) => {
              const numValue =
                property.type === "integer"
                  ? parseInt(e.target.value)
                  : parseFloat(e.target.value);
              handleChange(isNaN(numValue) ? "" : numValue);
            }}
            min={property.minimum}
            max={property.maximum}
            step={property.type === "integer" ? 1 : 0.1}
          />
          {property.description && (
            <p className="text-xs text-muted-foreground">
              {property.description}
            </p>
          )}
        </div>
      );
    }

    // Array fields (for simple arrays like retry_status_codes)
    if (property.type === "array") {
      const arrayValue = value || property.default || [];
      return (
        <div key={key} className="grid gap-2">
          <Label htmlFor={fieldId} className={isRequired ? "text-red-500" : ""}>
            {property.title || key}
            {isRequired && " *"}
          </Label>
          <Textarea
            id={fieldId}
            value={Array.isArray(arrayValue) ? arrayValue.join(", ") : ""}
            onChange={(e) => {
              const stringValue = e.target.value;
              const arrayValue = stringValue
                .split(",")
                .map((item) => item.trim())
                .filter((item) => item !== "")
                .map((item) => (isNaN(Number(item)) ? item : Number(item)));
              handleChange(arrayValue);
            }}
            placeholder="Comma-separated values"
          />
          {property.description && (
            <p className="text-xs text-muted-foreground">
              {property.description}
            </p>
          )}
        </div>
      );
    }

    // String fields with special formats
    if (property.type === "string") {
      const inputType = property.format === "password" ? "password" : "text";

      // Long text fields
      if (
        property.description?.includes("path") ||
        (property.maxLength && property.maxLength > 100)
      ) {
        return (
          <div key={key} className="grid gap-2">
            <Label
              htmlFor={fieldId}
              className={isRequired ? "text-red-500" : ""}
            >
              {property.title || key}
              {isRequired && " *"}
            </Label>
            <Textarea
              id={fieldId}
              value={value ?? property.default ?? ""}
              onChange={(e) => handleChange(e.target.value)}
              minLength={property.minLength}
              maxLength={property.maxLength}
              placeholder={property.description}
            />
            {property.description && (
              <p className="text-xs text-muted-foreground">
                {property.description}
              </p>
            )}
          </div>
        );
      }

      // Regular string inputs
      return (
        <div key={key} className="grid gap-2">
          <Label htmlFor={fieldId} className={isRequired ? "text-red-500" : ""}>
            {property.title || key}
            {isRequired && " *"}
          </Label>
          <Input
            id={fieldId}
            type={inputType}
            value={value ?? property.default ?? ""}
            onChange={(e) => handleChange(e.target.value)}
            minLength={property.minLength}
            maxLength={property.maxLength}
            placeholder={property.description}
          />
          {property.description && (
            <p className="text-xs text-muted-foreground">
              {property.description}
            </p>
          )}
        </div>
      );
    }

    // Fallback for unknown types
    console.log(`Unknown field type for ${key}:`, property);
    return (
      <div key={key} className="grid gap-2">
        <Label htmlFor={fieldId}>
          {property.title || key} (Unknown type: {property.type})
        </Label>
        <Input
          id={fieldId}
          value={JSON.stringify(value ?? property.default ?? "")}
          onChange={(e) => {
            try {
              handleChange(JSON.parse(e.target.value));
            } catch {
              handleChange(e.target.value);
            }
          }}
        />
      </div>
    );
  };

  // Helper function to resolve JSON Schema references
  const resolveRef = (
    refPath: string,
    schema: any,
  ): JSONSchemaProperty | null => {
    if (!refPath.startsWith("#/$defs/")) return null;
    const defName = refPath.replace("#/$defs/", "");
    return schema.$defs?.[defName] || null;
  };

  // Helper function to get properties from a section (handling allOf + $ref)
  const getSectionProperties = (sectionProperty: any, schema: any) => {
    // Direct properties
    if (sectionProperty.properties) {
      return sectionProperty.properties;
    }

    // Handle direct $ref (Pydantic style)
    if (sectionProperty.$ref) {
      const resolvedDef = resolveRef(sectionProperty.$ref, schema);
      return resolvedDef?.properties || null;
    }

    // Handle allOf with $ref
    if (sectionProperty.allOf && sectionProperty.allOf.length > 0) {
      const firstRef = sectionProperty.allOf[0];
      if (firstRef.$ref) {
        const resolvedDef = resolveRef(firstRef.$ref, schema);
        return resolvedDef?.properties || null;
      }
    }

    return null;
  };

  // If sectionKey is provided, only render that section
  if (sectionKey) {
    const sectionProperty = schema.properties[sectionKey];
    const sectionData = data?.[sectionKey];

    if (!sectionProperty) {
      return <div>Section "{sectionKey}" not found</div>;
    }

    const sectionProperties = getSectionProperties(sectionProperty, schema);

    if (!sectionProperties) {
      return <div>No properties found for section "{sectionKey}"</div>;
    }

    return (
      <div className="space-y-4">
        {Object.entries(sectionProperties).map(([key, property]) =>
          renderField(key, property as JSONSchemaProperty, sectionData?.[key], [
            sectionKey,
          ]),
        )}
      </div>
    );
  }

  // Render all sections
  return (
    <div className="space-y-6">
      {Object.entries(schema.properties).map(([key, property]) =>
        renderField(key, property, data[key]),
      )}
    </div>
  );
}

interface DynamicSectionCardProps {
  schema: JSONSchema;
  data: any;
  onChange: (path: string[], value: any) => void;
  sectionKey: string;
  title: string;
  description: string;
  icon: string;
}

export function DynamicSectionCard({
  schema,
  data,
  onChange,
  sectionKey,
  title,
  description,
  icon,
}: DynamicSectionCardProps) {
  // Get the icon component
  const IconComponent = (Icons as any)[icon] || Icons.Settings;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <IconComponent className="h-5 w-5" />
          {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <DynamicForm
          schema={schema}
          data={data}
          onChange={onChange}
          sectionKey={sectionKey}
        />
      </CardContent>
    </Card>
  );
}
