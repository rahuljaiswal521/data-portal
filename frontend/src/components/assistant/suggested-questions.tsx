"use client";

import { MessageSquare } from "lucide-react";

const SUGGESTIONS = [
  "What sources are currently configured?",
  "How does SCD2 work in this framework?",
  "How do I add a new source?",
  "When was the last successful run?",
  "What is the medallion architecture?",
  "How does data flow from Bronze to Gold?",
];

interface SuggestedQuestionsProps {
  onSelect: (question: string) => void;
}

export function SuggestedQuestions({ onSelect }: SuggestedQuestionsProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full py-16">
      <div className="flex items-center justify-center w-12 h-12 rounded-[var(--radius-lg)] bg-accent-light mb-4">
        <MessageSquare size={24} className="text-accent" />
      </div>
      <h3 className="text-lg font-semibold text-text-primary mb-1">
        Data Platform Assistant
      </h3>
      <p className="text-sm text-text-secondary mb-8 max-w-md text-center">
        Ask questions about your data lakehouse — Bronze ingestion, Silver
        transformations, Gold aggregations, or pipeline operations.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-lg w-full">
        {SUGGESTIONS.map((q) => (
          <button
            key={q}
            onClick={() => onSelect(q)}
            className="text-left px-4 py-3 rounded-[var(--radius-md)] border border-border
              text-sm text-text-secondary hover:text-text-primary hover:bg-bg-card-hover
              hover:border-border-hover transition-colors"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
