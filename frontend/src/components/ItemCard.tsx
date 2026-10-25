"use client";

import React, { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { PublicItem } from "@/lib/api";
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

  const letters = item.options.map((_, idx) => String.fromCharCode(65 + idx));
  return (
    <Card className="space-y-6 p-5 sm:p-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Badge tone="accent">Question</Badge>
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
            className="h-11 w-full rounded-lg border border-line bg-surface px-3.5 font-mono text-sm text-fg transition-colors focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent/15 disabled:opacity-70"
          />
        </div>
      )}

      {isChoice && (
        <div className="space-y-2.5" role="radiogroup" aria-label="Question options">
          {item.options.map((option, idx) => {
            const isSelected = selectedOption === option;
            const verdict = disabled && isSelected ? (isCorrect === true ? "right" : isCorrect === false ? "wrong" : null) : null;
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
                  "flex w-full items-start gap-3.5 rounded-xl border p-3.5 text-left transition-colors sm:p-4",
                  verdict === "right"
                    ? "border-success bg-success-soft"
                    : verdict === "wrong"
                      ? "border-danger bg-danger-soft"
                      : isSelected
                        ? "border-accent bg-accent-soft ring-1 ring-accent"
                        : "border-line bg-surface hover:border-line-strong hover:bg-surface-2",
                  disabled && !isSelected && "opacity-60"
                )}
              >
                <span
                  className={cn(
                    "mt-px flex h-6 w-6 flex-none items-center justify-center rounded-md border text-xs font-semibold transition-colors",
                    verdict === "right"
                      ? "border-success bg-success text-white"
                      : verdict === "wrong"
                        ? "border-danger bg-danger text-white"
                        : isSelected
                          ? "border-accent bg-accent text-accent-fg"
                          : "border-line text-muted"
                  )}
                  aria-hidden
                >
                  {letters[idx]}
                </span>
                <span className="self-center text-sm leading-relaxed text-fg">{option}</span>
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

function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="rounded border border-line bg-surface-2 px-1 py-px font-mono text-[11px] text-muted">{children}</kbd>;
}
