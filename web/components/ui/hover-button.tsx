"use client";
import * as React from "react";

export interface HoverSlatButtonProps
  extends React.HTMLAttributes<HTMLDivElement> {
  initialText: string;
  hoverText: string;
}

const HoverSlatButton = React.forwardRef<HTMLDivElement, HoverSlatButtonProps>(
  ({ initialText, hoverText, className, ...props }, ref) => {
    if (initialText.length !== hoverText.length) {
      console.error("HoverSlatButton: initialText and hoverText must be the same length.");
      return null;
    }

    return (
      <div
        ref={ref}
        className={`group flex cursor-pointer ${className ?? ""}`}
        {...props}
      >
        {initialText.split("").map((char, index) => (
          <div
            key={index}
            className="relative flex h-9 w-[1.85ch] items-center justify-center overflow-hidden bg-zinc-900 border-y border-r first:border-l first:rounded-l-md last:rounded-r-md border-green-400/20 text-[13px] font-bold text-green-400 transition-colors duration-300 group-hover:border-green-400/40"
            style={{ fontFamily: "monospace" }}
          >
            {/* Hover overlay — slides in from alternate directions */}
            <div
              className={`absolute inset-0 flex items-center justify-center bg-green-500 text-black transition-transform duration-300 ease-in-out ${
                index % 2 === 0 ? "translate-y-full" : "-translate-y-full"
              } group-hover:translate-y-0`}
              style={{ fontFamily: "monospace" }}
            >
              {hoverText[index]}
            </div>
            {/* Space renders as non-breaking so tiles keep their width */}
            {char === " " ? " " : char}
          </div>
        ))}
      </div>
    );
  }
);

HoverSlatButton.displayName = "HoverSlatButton";
export default HoverSlatButton;
