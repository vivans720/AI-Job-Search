"use client";

import React from "react";
import { RefreshCw } from "lucide-react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive" | "outline";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] text-white font-semibold border border-emerald-500/30 shadow-xs hover:shadow-sm disabled:opacity-50 disabled:pointer-events-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 focus-visible:outline-none",
  secondary:
    "bg-white hover:bg-slate-50 active:scale-[0.98] text-slate-700 hover:text-slate-900 border border-slate-200/90 hover:border-slate-300 shadow-xs disabled:opacity-50 disabled:pointer-events-none focus-visible:ring-2 focus-visible:ring-slate-400/20 focus-visible:outline-none",
  ghost:
    "bg-transparent hover:bg-slate-100 active:scale-[0.98] text-slate-600 hover:text-slate-900 disabled:opacity-40 disabled:pointer-events-none focus-visible:ring-2 focus-visible:ring-slate-400/20 focus-visible:outline-none",
  destructive:
    "bg-rose-50 hover:bg-rose-100 active:scale-[0.98] text-rose-700 hover:text-rose-800 border border-rose-200 disabled:opacity-50 disabled:pointer-events-none focus-visible:ring-2 focus-visible:ring-rose-400/50 focus-visible:outline-none",
  outline:
    "bg-white hover:bg-slate-50 active:scale-[0.98] text-slate-700 hover:text-slate-900 border border-slate-200 hover:border-slate-300 disabled:opacity-50 disabled:pointer-events-none focus-visible:ring-2 focus-visible:ring-slate-400/20 focus-visible:outline-none",
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: "px-2.5 py-1.5 text-xs rounded-lg gap-1.5 font-medium",
  md: "px-3.5 py-2 text-xs rounded-xl gap-2 font-medium",
  lg: "px-4 py-2.5 text-sm rounded-xl gap-2.5 font-medium",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      isLoading = false,
      leftIcon,
      rightIcon,
      children,
      disabled,
      className = "",
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={`inline-flex items-center justify-center transition-all cursor-pointer select-none ${
          variantStyles[variant]
        } ${sizeStyles[size]} ${className}`}
        {...props}
      >
        {isLoading ? (
          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
        ) : (
          leftIcon
        )}
        {children && <span>{children}</span>}
        {!isLoading && rightIcon}
      </button>
    );
  }
);

Button.displayName = "Button";
