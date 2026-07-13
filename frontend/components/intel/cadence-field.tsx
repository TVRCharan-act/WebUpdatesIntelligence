"use client";

import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CADENCE_UNITS, type CadenceUnit } from "@/lib/cadence";

// Number + unit picker for a check interval (minutes / hours / days / weeks /
// months). Parent holds `value` and `unit`; convert with toMinutes() on submit.

interface CadenceFieldProps {
  id?: string;
  value: string;
  unit: CadenceUnit;
  onValueChange: (value: string) => void;
  onUnitChange: (unit: CadenceUnit) => void;
  className?: string;
  compact?: boolean;
}

export function CadenceField({
  id,
  value,
  unit,
  onValueChange,
  onUnitChange,
  className,
  compact = false,
}: CadenceFieldProps) {
  return (
    <div className={`flex gap-2 ${className ?? ""}`}>
      <Input
        id={id}
        type="number"
        min={1}
        step={1}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        placeholder="1"
        className={compact ? "h-8 w-20" : "w-24"}
      />
      <Select value={unit} onValueChange={(v) => onUnitChange(v as CadenceUnit)}>
        <SelectTrigger className={compact ? "h-8 flex-1" : "flex-1"}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {CADENCE_UNITS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
