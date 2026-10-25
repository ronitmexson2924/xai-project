"use client";

import React, { useEffect, useRef, useState } from "react";
import { PublicItem } from "@/lib/api";

interface ItemCardProps {
  item: PublicItem;
  onAnswer: (response: string, latencyMs: number) => void;
  isSubmitting?: boolean;
  disabled?: boolean;
  selectedAnswer?: string | null;
  isCorrect?: boolean | null;
  conceptName?: string;
}

export function ItemCard({
  item,
  onAnswer,
  isSubmitting = false,
  disabled = false,
  selectedAnswer = null,
  isCorrect = null,
  conceptName,
}: ItemCardProps) {
  const [selectedOption, setSelectedOption] = useState<string | null>(selectedAnswer);
  const mountTimeRef = useRef<number>(0);

  // Initialize or reset latency timer when item changes
  useEffect(() => {
    const timer = setTimeout(() => {
      setSelectedOption(selectedAnswer);
      mountTimeRef.current = Date.now();
    }, 0);
    return () => clearTimeout(timer);
  }, [item.id, selectedAnswer]);

  const handleSubmit = React.useCallback(() => {
    if (!selectedOption || !selectedOption.trim() || disabled || isSubmitting) return;
    const start = mountTimeRef.current > 0 ? mountTimeRef.current : Date.now();
    const latencyMs = Math.max(50, Date.now() - start);
    onAnswer(selectedOption, latencyMs);
  }, [selectedOption, disabled, isSubmitting, onAnswer]);

  // Keyboard accessibility: 1-4, A-D to select; Enter to submit
  const isChoice = item.options.length > 0;

  useEffect(() => {
    if (disabled || !isChoice) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger if user is in an input field
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      const key = e.key.toUpperCase();
      if (key === "ENTER") {
        e.preventDefault();
        handleSubmit();
        return;
      }

      let optionIndex = -1;
      if (["1", "2", "3", "4", "5", "6"].includes(key)) {
        optionIndex = parseInt(key, 10) - 1;
      } else if (["A", "B", "C", "D", "E", "F"].includes(key)) {
        optionIndex = key.charCodeAt(0) - 65;
      }

      if (optionIndex >= 0 && optionIndex < item.options.length) {
        e.preventDefault();
        setSelectedOption(item.options[optionIndex]);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [disabled, isChoice, item.options, selectedOption, isSubmitting, handleSubmit]);

  // Render question stem, highlighting code blocks if present
  const renderStem = (stemText: string) => {
    // If stem has markdown code fence
    if (stemText.includes("```")) {
      const parts = stemText.split(/(```[\s\S]*?```)/g);
      return parts.map((part, idx) => {
        if (part.startsWith("```") && part.endsWith("```")) {
          const lines = part.slice(3, -3).trim().split("\n");
          // Remove optional language identifier
          const code = (lines[0].match(/^[a-z]+$/) ? lines.slice(1) : lines).join("\n");
          return (
            <pre
              key={idx}
              className="my-3 p-3.5 rounded-xl bg-slate-950 font-mono text-xs text-indigo-300 border border-slate-800 overflow-x-auto"
            >
              <code>{code}</code>
            </pre>
          );
        }
        return (
          <p key={idx} className="whitespace-pre-line">
            {part}
          </p>
        );
      });
    }

    return <p className="whitespace-pre-line">{stemText}</p>;
  };

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 sm:p-7 shadow-2xl backdrop-blur-xl space-y-6">
      {/* Item Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-indigo-500" />
          <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">
            Concept Check
          </span>
          {conceptName && (
            <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
              {conceptName}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-500 uppercase">{item.kind}</span>
          <span className={isChoice ? "text-[11px] text-slate-500 hidden sm:inline" : "hidden"}>
            (Shortcuts: <kbd className="px-1 py-0.5 rounded bg-slate-800 font-mono text-[10px]">A-D</kbd> or <kbd className="px-1 py-0.5 rounded bg-slate-800 font-mono text-[10px]">1-4</kbd>)
          </span>
        </div>
      </div>

      {/* Stem */}
      <div className="text-sm sm:text-base text-slate-100 font-medium leading-relaxed">
        {renderStem(item.stem)}
      </div>

      {/* Free-text answer for short and code-trace questions */}
      {!isChoice && (
        <div className="space-y-2">
          <label htmlFor={`answer-${item.id}`} className="text-xs text-slate-400">
            Your answer
          </label>
          <input
            id={`answer-${item.id}`}
            type="text"
            maxLength={2000}
            autoComplete="off"
            value={selectedOption ?? ""}
            disabled={disabled || isSubmitting}
            onChange={(e) => setSelectedOption(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleSubmit();
              }
            }}
            className="w-full rounded-xl border border-slate-700 bg-slate-950/60 px-4 py-3 text-sm text-white font-mono focus:border-indigo-500 focus:outline-none"
          />
        </div>
      )}

      {/* Options */}
      <div className={isChoice ? "space-y-3" : "hidden"} role="radiogroup" aria-label="Question options">
        {item.options.map((option, idx) => {
          const letter = String.fromCharCode(65 + idx);
          const isSelected = selectedOption === option;

          let optionStyle =
            "border-slate-800 bg-slate-950/50 hover:border-slate-700 hover:bg-slate-950/80 text-slate-300";
          let badgeStyle = "bg-slate-800 text-slate-400 border-slate-700";

          if (isSelected) {
            optionStyle =
              "border-indigo-500 bg-indigo-500/10 text-white shadow-md shadow-indigo-500/10 ring-1 ring-indigo-500";
            badgeStyle = "bg-indigo-600 text-white border-indigo-500";
          }

          if (disabled && isSelected) {
            if (isCorrect === true) {
              optionStyle =
                "border-emerald-500 bg-emerald-500/10 text-emerald-200 ring-1 ring-emerald-500";
              badgeStyle = "bg-emerald-600 text-white border-emerald-500";
            } else if (isCorrect === false) {
              optionStyle =
                "border-rose-500 bg-rose-500/10 text-rose-200 ring-1 ring-rose-500";
              badgeStyle = "bg-rose-600 text-white border-rose-500";
            }
          }

          return (
            <button
              key={`${item.id}-opt-${idx}`}
              type="button"
              role="radio"
              aria-checked={isSelected}
              disabled={disabled || isSubmitting}
              onClick={() => setSelectedOption(option)}
              className={`w-full text-left p-3.5 sm:p-4 rounded-xl border transition-all flex items-start gap-3.5 ${optionStyle}`}
            >
              <div
                className={`w-6 h-6 rounded-lg border flex items-center justify-center font-bold text-xs shrink-0 mt-0.5 transition-colors ${badgeStyle}`}
              >
                {letter}
              </div>
              <span className="text-xs sm:text-sm leading-relaxed self-center">{option}</span>
            </button>
          );
        })}
      </div>

      {/* Submission CTA */}
      {!disabled && (
        <div className="pt-2 flex items-center justify-between">
          <span className="text-xs text-slate-500 hidden sm:inline">
            Press <kbd className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[11px]">Enter ↵</kbd> to submit
          </span>
          <button
            type="button"
            disabled={!selectedOption || isSubmitting}
            onClick={handleSubmit}
            className={`w-full sm:w-auto px-6 py-2.5 rounded-xl font-semibold text-sm transition-all shadow-md ${
              selectedOption && !isSubmitting
                ? "bg-indigo-600 hover:bg-indigo-500 text-white shadow-indigo-600/30"
                : "bg-slate-800 text-slate-500 cursor-not-allowed border border-slate-700/50"
            }`}
          >
            {isSubmitting ? "Submitting answer..." : "Submit Answer"}
          </button>
        </div>
      )}
    </div>
  );
}
