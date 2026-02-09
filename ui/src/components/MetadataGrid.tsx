import { FC } from "react";

export type MetadataEntry = {
  label: string;
  value: string;
};

type MetadataGridProps = {
  entries: MetadataEntry[];
  className?: string;
  itemClassName?: string;
};

/**
 * Renders label/value metadata pairs in a responsive grid.
 * Falls back to null if no entries are provided.
 */
export const MetadataGrid: FC<MetadataGridProps> = ({
  entries,
  className = "",
  itemClassName = "flex flex-col",
}) => {
  if (!entries || entries.length === 0) {
    return null;
  }

  const baseClasses = "grid gap-x-6 gap-y-3 text-[11px] text-slate-500 sm:grid-cols-2 sm:text-xs";
  const combinedClassName = className ? `${baseClasses} ${className}` : baseClasses;

  return (
    <div className={combinedClassName}>
      {entries.map(({ label, value }, index) => (
        <div key={`${label}-${index}`} className={itemClassName}>
          <span className="font-semibold text-slate-600">{label}</span>
          <span className="break-all">{value}</span>
        </div>
      ))}
    </div>
  );
};
