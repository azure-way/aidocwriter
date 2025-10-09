import { cn } from "@/lib/utils";
import React from "react";

export function GlassCard({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("glass-panel border border-white/10 px-7 py-8", className)}>{children}</div>;
}
