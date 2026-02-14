"use client";

import { useEffect, useRef } from "react";
import { ChatInput } from "./chat-input";
import { ChatMessage } from "./chat-message";
import { SuggestedQuestions } from "./suggested-questions";
import { useChat } from "@/hooks/use-chat";
import { Button } from "@/components/ui/button";
import { Bot, Trash2 } from "lucide-react";

export function ChatContainer() {
  const { messages, isLoading, error, sendMessage, clearChat } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] rounded-[var(--radius-lg)] border border-border bg-bg-card shadow-[var(--shadow-sm)]">
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <Bot size={16} className="text-accent" />
          <h3 className="text-sm font-semibold text-text-primary">
            Data Platform Assistant
          </h3>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={clearChat}
          disabled={messages.length === 0}
        >
          <Trash2 size={14} />
          Clear
        </Button>
      </div>

      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4">
        {messages.length === 0 ? (
          <SuggestedQuestions onSelect={sendMessage} />
        ) : (
          <>
            {messages.map((msg, i) => (
              <ChatMessage key={i} message={msg} />
            ))}
            {isLoading && (
              <div className="flex gap-3 py-4">
                <div className="flex-shrink-0 w-8 h-8 rounded-[var(--radius-md)] bg-accent-light flex items-center justify-center">
                  <Bot size={16} className="text-accent animate-pulse" />
                </div>
                <div className="bg-bg-secondary rounded-[var(--radius-lg)] px-4 py-3">
                  <div className="flex gap-1">
                    <span
                      className="w-2 h-2 rounded-full bg-text-tertiary animate-bounce"
                      style={{ animationDelay: "0ms" }}
                    />
                    <span
                      className="w-2 h-2 rounded-full bg-text-tertiary animate-bounce"
                      style={{ animationDelay: "150ms" }}
                    />
                    <span
                      className="w-2 h-2 rounded-full bg-text-tertiary animate-bounce"
                      style={{ animationDelay: "300ms" }}
                    />
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        {error && (
          <div className="mx-4 mb-4 px-4 py-3 rounded-[var(--radius-md)] border border-error bg-[rgba(196,75,59,0.05)] text-sm text-error">
            {error}
          </div>
        )}
      </div>

      {/* Input */}
      <ChatInput onSend={sendMessage} disabled={isLoading} />
    </div>
  );
}
