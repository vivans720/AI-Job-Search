"use client";

import React from "react";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "surface" | "interactive" | "well";
  padding?: "none" | "sm" | "md" | "lg";
}

const variantStyles = {
  surface: "bg-white border border-slate-200/80 shadow-card-subtle",
  interactive:
    "bg-white border border-slate-200/80 shadow-card-subtle hover:border-slate-300 hover:shadow-card-hover transition-all duration-150",
  well: "bg-slate-50 border border-slate-200/70",
};

const paddingStyles = {
  none: "p-0",
  sm: "p-3",
  md: "p-4 sm:p-5",
  lg: "p-6",
};

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ variant = "surface", padding = "md", className = "", children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={`rounded-xl ${variantStyles[variant]} ${paddingStyles[padding]} ${className}`}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = "Card";
