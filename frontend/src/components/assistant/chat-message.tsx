"use client";

import { cn } from "@/lib/utils";
import { Bot, User } from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { ChatMessage as ChatMessageType } from "@/types";

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex gap-3 py-4",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-[var(--radius-md)] bg-accent-light flex items-center justify-center">
          <Bot size={16} className="text-accent" />
        </div>
      )}
      <div
        className={cn(
          "max-w-[75%] rounded-[var(--radius-lg)] px-4 py-3 text-sm",
          isUser
            ? "bg-bg-dark text-text-inverse"
            : "bg-bg-card border border-border text-text-primary"
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-sm max-w-none prose-pre:bg-bg-secondary prose-pre:text-text-primary prose-pre:rounded-[var(--radius-md)] prose-pre:text-xs prose-code:text-accent prose-code:text-xs prose-p:my-1.5 prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5 prose-headings:my-2 prose-headings:text-text-primary">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}
        {!isUser && message.sources_used && message.sources_used.length > 0 && (
          <div className="mt-2 pt-2 border-t border-border">
            <p className="text-[11px] text-text-tertiary">
              Sources: {message.sources_used.join(", ")}
            </p>
          </div>
        )}
      </div>
      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 rounded-[var(--radius-md)] bg-bg-secondary flex items-center justify-center">
          <User size={16} className="text-text-secondary" />
        </div>
      )}
    </div>
  );
}
