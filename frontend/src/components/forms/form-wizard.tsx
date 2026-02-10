"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Check } from "lucide-react";
import { useState } from "react";

interface Step {
  id: string;
  title: string;
  description: string;
  content: React.ReactNode;
}

interface FormWizardProps {
  steps: Step[];
  onSubmit: () => void;
  submitting?: boolean;
}

export function FormWizard({ steps, onSubmit, submitting }: FormWizardProps) {
  const [currentStep, setCurrentStep] = useState(0);

  const isLast = currentStep === steps.length - 1;

  return (
    <div className="flex gap-8">
      {/* Step indicator */}
      <div className="w-[220px] shrink-0">
        <nav className="space-y-1">
          {steps.map((step, i) => (
            <button
              key={step.id}
              onClick={() => setCurrentStep(i)}
              className={cn(
                "w-full flex items-center gap-3 px-3 py-2.5 rounded-[var(--radius-md)] text-left transition-colors",
                i === currentStep
                  ? "bg-accent-light"
                  : "hover:bg-bg-secondary"
              )}
            >
              <span
                className={cn(
                  "flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium shrink-0",
                  i < currentStep
                    ? "bg-accent text-white"
                    : i === currentStep
                    ? "bg-bg-dark text-text-inverse"
                    : "bg-bg-secondary text-text-tertiary"
                )}
              >
                {i < currentStep ? <Check size={12} /> : i + 1}
              </span>
              <div>
                <p
                  className={cn(
                    "text-sm font-medium leading-tight",
                    i === currentStep
                      ? "text-accent"
                      : "text-text-secondary"
                  )}
                >
                  {step.title}
                </p>
                <p className="text-[11px] text-text-tertiary leading-tight mt-0.5">
                  {step.description}
                </p>
              </div>
            </button>
          ))}
        </nav>
      </div>

      {/* Step content */}
      <div className="flex-1 min-w-0">
        <div className="rounded-[var(--radius-lg)] border border-border bg-bg-card p-6">
          <h3 className="text-lg font-semibold text-text-primary mb-1">
            {steps[currentStep].title}
          </h3>
          <p className="text-sm text-text-secondary mb-6">
            {steps[currentStep].description}
          </p>

          {steps[currentStep].content}

          <div className="flex justify-between mt-8 pt-6 border-t border-border">
            <Button
              variant="secondary"
              onClick={() => setCurrentStep((s) => s - 1)}
              disabled={currentStep === 0}
            >
              Previous
            </Button>
            {isLast ? (
              <Button onClick={onSubmit} disabled={submitting}>
                {submitting ? "Creating..." : "Create Source"}
              </Button>
            ) : (
              <Button onClick={() => setCurrentStep((s) => s + 1)}>
                Continue
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
