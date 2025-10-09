import React from "react";

interface GradientTitleProps {
  title: string;
  subtitle?: string;
  className?: string;
  subtitleClassName?: string;
}

export function GradientTitle({
  title,
  subtitle,
  className,
  subtitleClassName,
}: GradientTitleProps) {
  return (
    <div className="mb-6">
      <h2
        className={[
          "bg-gradient-to-r from-purple-400 via-rose-200 to-sky-400 bg-clip-text text-2xl font-semibold text-transparent md:text-3xl",
          className,
        ]
          .filter(Boolean)
          .join(" ")}
      >
        {title}
      </h2>
      {subtitle ? (
        <p className={["mt-2 text-sm text-slate-500", subtitleClassName].filter(Boolean).join(" ")}>{subtitle}</p>
      ) : null}
    </div>
  );
}
