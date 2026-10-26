"use client";

import React, { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { PublicItem } from "@/lib/api";
import { ENGAGEMENT_UI } from "@/lib/engagement";
import { Markdown } from "./Markdown";
import { Badge } from "./ui/Badge";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";
import { cn } from "./ui/cn";

interface ItemCardProps {
  item: PublicItem;
  onAnswer: (response: string, latencyMs: number) => void;
  isSubmitting?: boolean;
  disabled?: boolean;
  selectedAnswer?: string | null;
  isCorrect?: boolean | null;
  /** the expected answer, once the server has marked the attempt (revealed after a wrong answer) */
  correctAnswer?: string | null;
  conceptName?: string;
}

export function ItemCard({
  item,
  onAnswer,
  isSubmitting = false,
  disabled = false,
  selectedAnswer = null,
  isCorrect = null,
  correctAnswer = null,
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

  const letters = item.options.map((_, idx) => String.fromCharCode(65 + idx));
  return (
    <Card className="space-y-6 p-5 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Badge tone="primary">Question</Badge>
          {conceptName && <span className="text-sm text-muted">{conceptName}</span>}
        </div>
        {isChoice && !disabled && (
          <span className="hidden text-xs text-subtle sm:inline">
            Keys <Kbd>A</Kbd>–<Kbd>{letters[letters.length - 1]}</Kbd> to choose, <Kbd>Enter</Kbd> to submit
          </span>
        )}
      </div>

      <div className="text-base font-medium leading-relaxed text-fg">
        <Markdown text={item.stem} />
      </div>

      {!isChoice && (
        <div className="space-y-2">
          <label htmlFor={`answer-${item.id}`} className="text-sm font-medium text-fg">
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
            className="h-11 w-full rounded-lg border border-line bg-surface px-3.5 font-mono text-sm text-fg transition-colors focus:border-primary focus:outline-none focus:ring-4 focus:ring-primary/15 disabled:opacity-70"
          />
        </div>
      )}

      {isChoice && (
        <div className="space-y-2.5" role="radiogroup" aria-label="Question options">
          {item.options.map((option, idx) => {
            const isSelected = selectedOption === option;
            // after marking: your pick is right (green, ✓) or wrong (neutral, ✕); a wrong pick also
            // reveals the expected option. Never colour alone: each state has its own icon and text.
            const verdict = disabled
              ? isSelected && isCorrect === true
                ? "right"
                : isSelected && isCorrect === false
                  ? "wrong"
                  : isCorrect === false && option === correctAnswer
                    ? "answer"
                    : null
              : null;
            const note = verdict === "right" ? "you chose this: correct" : verdict === "wrong" ? "you chose this: incorrect" : verdict === "answer" ? "the correct answer" : null;
            return (
              <motion.button
                key={`${item.id}-opt-${idx}`}
                type="button"
                role="radio"
                aria-checked={isSelected}
                disabled={disabled || isSubmitting}
                onClick={() => setSelectedOption(option)}
                whileTap={{ scale: 0.99 }}
                className={cn(
                  "group flex w-full items-start gap-3.5 rounded-lg border p-3.5 text-left transition-[background-color,border-color,transform] duration-150 sm:p-4",
                  verdict === "right" || verdict === "answer"
                    ? "border-success bg-success-soft"
                    : verdict === "wrong"
                      ? "border-line-strong bg-surface-2"
                      : isSelected
                        ? "border-primary bg-primary-soft"
                        : "border-line bg-surface hover:border-line-strong hover:bg-surface-2",
                  ENGAGEMENT_UI && !disabled && !isSelected && "hover:-translate-y-px",
                  disabled && !verdict && "opacity-60"
                )}
              >
                <span
                  className={cn(
                    "mt-px flex h-6 w-6 flex-none items-center justify-center rounded-md border text-xs font-semibold transition-colors",
                    verdict === "right" || verdict === "answer"
                      ? "border-success bg-success text-white"
                      : verdict === "wrong"
                        ? "border-line-strong bg-surface text-muted"
                        : isSelected
                          ? "border-primary bg-primary text-primary-fg"
                          : cn("border-line text-muted", ENGAGEMENT_UI && "group-hover:border-primary/40 group-hover:text-primary")
                  )}
                  aria-hidden
                >
                  {verdict === "right" || verdict === "answer" ? <Tick /> : verdict === "wrong" ? <Cross /> : letters[idx]}
                </span>
                <span className="flex flex-1 flex-wrap items-center justify-between gap-x-3 gap-y-1 self-center">
                  <span className="text-sm leading-relaxed text-fg">
                    {option}
                    {note && <span className="sr-only"> ({note})</span>}
                  </span>
                  {verdict === "answer" && <span className="text-xs font-medium text-success" aria-hidden>Correct answer</span>}
                  {verdict === "wrong" && <span className="text-xs font-medium text-muted" aria-hidden>Your answer</span>}
                </span>
              </motion.button>
            );
          })}
        </div>
      )}

      {!disabled && (
        <div className="flex justify-end">
          <Button onClick={handleSubmit} disabled={!selectedOption?.trim()} loading={isSubmitting} className="w-full sm:w-auto">
            Submit answer
          </Button>
        </div>
      )}
    </Card>
  );
}

function Tick() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 12.5 10 17.5 19 7" />
    </svg>
  );
}

function Cross() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="rounded border border-line bg-surface-2 px-1 py-px font-mono text-[11px] text-muted">{children}</kbd>;
}
