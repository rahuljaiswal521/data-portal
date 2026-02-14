"use client";

import { cn } from "@/lib/utils";
import { Send } from "lucide-react";
import { useRef, useState, type KeyboardEvent } from "react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = "Ask about your data pipelines...",
}: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        Math.min(textareaRef.current.scrollHeight, 150) + "px";
    }
  };

  return (
    <div className="flex items-end gap-2 p-4 border-t border-border bg-bg-card">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        className={cn(
          "flex-1 resize-none rounded-[var(--radius-md)] border border-border",
          "bg-bg-primary px-4 py-2.5 text-sm text-text-primary",
          "placeholder:text-text-tertiary",
          "focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent",
          "disabled:opacity-50"
        )}
      />
      <button
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        className={cn(
          "flex items-center justify-center w-10 h-10 rounded-[var(--radius-md)]",
          "bg-bg-dark text-text-inverse transition-colors",
          "hover:bg-[#2d2d2c] disabled:opacity-50 disabled:pointer-events-none"
        )}
      >
        <Send size={16} />
      </button>
    </div>
  );
}
