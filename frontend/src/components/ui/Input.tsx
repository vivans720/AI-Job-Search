"use client";

import React from "react";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className = "", error = false, leftIcon, rightIcon, disabled, ...props }, ref) => {
    return (
      <div className="relative flex items-center w-full">
        {leftIcon && (
          <div className="absolute left-3 flex items-center pointer-events-none text-slate-400">
            {leftIcon}
          </div>
        )}
        <input
          ref={ref}
          disabled={disabled}
          className={`w-full bg-white text-slate-900 placeholder:text-slate-400 text-xs rounded-xl border transition-all shadow-xs ${
            error
              ? "border-rose-300 focus:border-rose-500 focus:ring-2 focus:ring-rose-500/20"
              : "border-slate-200/90 hover:border-slate-300 focus:border-slate-400 focus:ring-2 focus:ring-slate-400/20"
          } ${leftIcon ? "pl-9" : "pl-3.5"} ${rightIcon ? "pr-9" : "pr-3.5"} py-2.5 disabled:opacity-50 disabled:bg-slate-50 disabled:cursor-not-allowed outline-none ${className}`}
          {...props}
        />
        {rightIcon && (
          <div className="absolute right-3 flex items-center pointer-events-none text-slate-400">
            {rightIcon}
          </div>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
