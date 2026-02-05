import { FC, ReactNode } from "react";
import { MetadataGrid, MetadataEntry } from "@/components/MetadataGrid";

type TimelineStageDetailsProps = {
  sourceStageLabel?: string;
  showSourceStage?: boolean;
  metadataEntries: MetadataEntry[];
  message?: string;
  showMessage?: boolean;
  artifact?: string;
  renderArtifactActions?: (artifact: string, size?: "sm" | "md", stageBase?: string) => ReactNode;
  stageBase?: string;
  children?: ReactNode;
};

export const TimelineStageDetails: FC<TimelineStageDetailsProps> = ({
  sourceStageLabel,
  showSourceStage = false,
  metadataEntries,
  message,
  showMessage = false,
  artifact,
  renderArtifactActions,
  stageBase,
  children,
}) => (
  <div className="space-y-3 border-t border-slate-100 pt-3">
    {showSourceStage && sourceStageLabel ? (
      <p className="text-xs text-slate-400">{sourceStageLabel}</p>
    ) : null}
    {metadataEntries.length > 0 ? (
      <MetadataGrid entries={metadataEntries} />
    ) : showMessage && message ? (
      <p className="text-xs text-slate-500">{message}</p>
    ) : null}
    {artifact && renderArtifactActions ? renderArtifactActions(artifact, "sm", stageBase) : null}
    {children}
  </div>
);
