"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Sparkles,
  Send,
  Bot,
  User,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Plus,
  Trash2,
  FileCheck2,
  Shield,
  HelpCircle,
  ArrowRight,
  RefreshCw,
} from "lucide-react";
import { assistantApi } from "@/lib/api";
import type {
  AskResponsePayload,
  AssistantConversationRead,
  AssistantMessageRead,
  StructuredAssistantResponse,
} from "@/types/assistant";

const CANONICAL_QUESTIONS = [
  "What should I focus on today?",
  "Which project is falling behind?",
  "Why do I keep postponing this task?",
  "Which tasks are blocking my current goal?",
  "What changed in my productivity this month?",
  "Which recommendations have worked well historically?",
];

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  structuredResponse?: StructuredAssistantResponse | null;
  createdAt: string;
}

export function ConversationalAssistant() {
  const [conversations, setConversations] = useState<AssistantConversationRead[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [expandedEvidence, setExpandedEvidence] = useState<Record<string, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load conversation list on mount
  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    try {
      const res = await assistantApi.listConversations();
      setConversations(res.conversations);
      if (res.conversations.length > 0 && !activeConversationId) {
        selectConversation(res.conversations[0].id);
      }
    } catch (err) {
      console.error("Failed to load conversations:", err);
    }
  };

  const selectConversation = async (convId: string) => {
    setActiveConversationId(convId);
    try {
      const data = await assistantApi.getConversation(convId);
      const chatMsgs: ChatMessage[] = data.recent_messages.map((m) => ({
        id: m.id,
        role: m.role as "user" | "assistant",
        content: m.content,
        structuredResponse: m.structured_response,
        createdAt: m.created_at,
      }));
      setMessages(chatMsgs);
    } catch (err) {
      console.error("Failed to fetch conversation history:", err);
    }
  };

  const startNewConversation = () => {
    setActiveConversationId(null);
    setMessages([]);
    setInputValue("");
  };

  const deleteConversation = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await assistantApi.deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConversationId === convId) {
        startNewConversation();
      }
    } catch (err) {
      console.error("Failed to archive conversation:", err);
    }
  };

  const handleSend = async (queryText?: string) => {
    const q = (queryText || inputValue).trim();
    if (!q || isLoading) return;

    setInputValue("");

    // Add user message to UI immediately
    const userMsg: ChatMessage = {
      id: `temp-u-${Date.now()}`,
      role: "user",
      content: q,
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const res: AskResponsePayload = await assistantApi.ask({
        query: q,
        conversation_id: activeConversationId,
        include_evidence: true,
        include_proposals: true,
      });

      if (!activeConversationId) {
        setActiveConversationId(res.conversation_id);
        loadConversations();
      }

      const assistantMsg: ChatMessage = {
        id: res.message_id,
        role: "assistant",
        content: res.response.direct_answer,
        structuredResponse: res.response,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      console.error("Error asking assistant:", err);
      const errMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: "Sorry, I encountered an error retrieving data for your query. Please try again.",
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const toggleEvidence = (msgId: string) => {
    setExpandedEvidence((prev) => ({
      ...prev,
      [msgId]: !prev[msgId],
    }));
  };

  const getUncertaintyBadge = (level?: string) => {
    switch (level) {
      case "LOW":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
            <CheckCircle2 className="h-3 w-3" /> Grounded High Confidence
          </span>
        );
      case "MEDIUM":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-950/40 dark:text-amber-400">
            <AlertTriangle className="h-3 w-3" /> Moderate Evidence
          </span>
        );
      case "HIGH":
      case "UNCERTAIN":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700 dark:bg-rose-950/40 dark:text-rose-400">
            <HelpCircle className="h-3 w-3" /> Limited Telemetry / Uncertain
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-4 md:flex-row">
      {/* Sidebar: Conversation Sessions */}
      <aside className="flex w-full flex-col rounded-xl border border-border bg-card p-4 md:w-72">
        <div className="flex items-center justify-between pb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <span className="font-semibold text-foreground">Conversations</span>
          </div>
          <button
            onClick={startNewConversation}
            className="inline-flex items-center gap-1 rounded-lg bg-primary/10 px-2.5 py-1.5 text-xs font-medium text-primary hover:bg-primary/20"
          >
            <Plus className="h-3.5 w-3.5" /> New
          </button>
        </div>

        <div className="flex-1 space-y-1.5 overflow-y-auto pr-1">
          {conversations.length === 0 ? (
            <p className="py-8 text-center text-xs text-muted-foreground">No recent conversations.</p>
          ) : (
            conversations.map((c) => {
              const isActive = activeConversationId === c.id;
              return (
                <div
                  key={c.id}
                  onClick={() => selectConversation(c.id)}
                  className={`group flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-xs transition-colors ${
                    isActive
                      ? "bg-primary text-primary-foreground font-medium"
                      : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  }`}
                >
                  <span className="truncate pr-2">{c.title || "Conversation"}</span>
                  <button
                    onClick={(e) => deleteConversation(c.id, e)}
                    className={`opacity-0 group-hover:opacity-100 ${
                      isActive ? "text-primary-foreground/80 hover:text-white" : "text-muted-foreground hover:text-rose-500"
                    }`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>

        <div className="mt-3 border-t border-border pt-3 text-[11px] text-muted-foreground flex items-center gap-1.5">
          <Shield className="h-3.5 w-3.5 text-muted-foreground" />
          <span>Strict user data isolation active.</span>
        </div>
      </aside>

      {/* Main Chat Interface */}
      <main className="flex flex-1 flex-col rounded-xl border border-border bg-card">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Bot className="h-4 w-4" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-foreground">ContextIQ Productivity Assistant</h1>
              <p className="text-[11px] text-muted-foreground">
                Knowledge-grounded answers based strictly on your verified workspace data
              </p>
            </div>
          </div>
          {activeConversationId && (
            <button
              onClick={startNewConversation}
              className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
            >
              <RefreshCw className="h-3 w-3" /> Reset Chat
            </button>
          )}
        </div>

        {/* Message Feed */}
        <div className="flex-1 space-y-4 overflow-y-auto p-5">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary mb-3">
                <Sparkles className="h-6 w-6" />
              </div>
              <h2 className="text-base font-semibold text-foreground">How can I assist your productivity?</h2>
              <p className="mt-1 max-w-md text-xs text-muted-foreground">
                Ask anything regarding your schedule, projects, overdue tasks, blockers, or long-term behavioral trends.
              </p>

              {/* Quick Prompts */}
              <div className="mt-6 grid w-full max-w-xl grid-cols-1 gap-2 sm:grid-cols-2 text-left">
                {CANONICAL_QUESTIONS.map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSend(q)}
                    className="flex items-center justify-between rounded-lg border border-border bg-background p-2.5 text-xs text-muted-foreground hover:border-primary/50 hover:bg-accent hover:text-foreground transition-all"
                  >
                    <span>{q}</span>
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 opacity-60" />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => {
              const isUser = m.role === "user";
              const sr = m.structuredResponse;
              const isEvExpanded = expandedEvidence[m.id];

              return (
                <div
                  key={m.id}
                  className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
                >
                  {!isUser && (
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary mt-0.5">
                      <Bot className="h-3.5 w-3.5" />
                    </div>
                  )}

                  <div
                    className={`max-w-[85%] rounded-2xl p-4 text-xs ${
                      isUser
                        ? "bg-primary text-primary-foreground rounded-tr-none"
                        : "border border-border bg-background rounded-tl-none space-y-3"
                    }`}
                  >
                    {/* User Prompt */}
                    {isUser ? (
                      <p className="whitespace-pre-wrap">{m.content}</p>
                    ) : (
                      <>
                        {/* Direct Answer */}
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between gap-2 pb-1">
                            {getUncertaintyBadge(sr?.uncertainty_level)}
                            {sr?.data_timestamps?.tasks && (
                              <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                                <Clock className="h-2.5 w-2.5" /> Verified
                              </span>
                            )}
                          </div>
                          <div className="text-foreground whitespace-pre-wrap leading-relaxed text-sm">
                            {m.content}
                          </div>
                        </div>

                        {/* Missing Information Alert */}
                        {sr?.missing_information && sr.missing_information.length > 0 && (
                          <div className="rounded-lg bg-amber-50 p-2.5 text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
                            <div className="flex items-center gap-1.5 font-medium text-[11px]">
                              <AlertTriangle className="h-3.5 w-3.5" /> Unobserved Data
                            </div>
                            <ul className="mt-1 list-disc pl-4 text-[11px] space-y-0.5">
                              {sr.missing_information.map((info, idx) => (
                                <li key={idx}>{info}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Linked Entities */}
                        {sr?.relevant_entities && sr.relevant_entities.length > 0 && (
                          <div className="pt-1">
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                              Referenced Entities
                            </span>
                            <div className="mt-1.5 flex flex-wrap gap-1.5">
                              {sr.relevant_entities.map((ent, idx) => (
                                <span
                                  key={idx}
                                  className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2 py-1 text-[11px] font-medium text-foreground"
                                >
                                  <span className="text-[9px] uppercase px-1 py-0.2 rounded bg-muted text-muted-foreground font-mono">
                                    {ent.entity_type}
                                  </span>
                                  {ent.title}
                                  {ent.status && (
                                    <span className="text-[10px] text-muted-foreground font-normal">
                                      ({ent.status})
                                    </span>
                                  )}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Action Proposals */}
                        {sr?.action_proposals && sr.action_proposals.length > 0 && (
                          <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="inline-flex items-center gap-1.5 font-semibold text-primary text-[11px]">
                                <FileCheck2 className="h-3.5 w-3.5" /> Proposed Governed Action
                              </span>
                              <span className="text-[10px] bg-primary/20 text-primary px-1.5 py-0.5 rounded font-mono">
                                Phase 7 Governed
                              </span>
                            </div>
                            {sr.action_proposals.map((prop, idx) => (
                              <div key={idx} className="space-y-1">
                                <p className="font-medium text-foreground text-xs font-mono">{prop.action_identifier}</p>
                                <p className="text-[11px] text-muted-foreground">{prop.rationale}</p>
                                <div className="pt-1 flex items-center justify-between">
                                  <span className="text-[10px] text-amber-600 dark:text-amber-400">
                                    Requires explicit user approval
                                  </span>
                                  <a
                                    href="/workflows"
                                    className="inline-flex items-center gap-1 rounded bg-primary px-2 py-1 text-[10px] font-medium text-primary-foreground hover:bg-primary/90"
                                  >
                                    Review in Governance <ExternalLink className="h-2.5 w-2.5" />
                                  </a>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Supporting Evidence Drawer */}
                        {sr?.supporting_evidence && sr.supporting_evidence.length > 0 && (
                          <div className="border-t border-border pt-2">
                            <button
                              onClick={() => toggleEvidence(m.id)}
                              className="flex w-full items-center justify-between text-[11px] font-medium text-muted-foreground hover:text-foreground"
                            >
                              <span>Supporting Evidence ({sr.supporting_evidence.length})</span>
                              {isEvExpanded ? (
                                <ChevronDown className="h-3.5 w-3.5" />
                              ) : (
                                <ChevronRight className="h-3.5 w-3.5" />
                              )}
                            </button>

                            {isEvExpanded && (
                              <div className="mt-2 space-y-1.5 pl-1">
                                {sr.supporting_evidence.map((ev, idx) => (
                                  <div
                                    key={idx}
                                    className="rounded-md border border-border bg-card p-2 text-[11px] space-y-0.5"
                                  >
                                    <div className="flex items-center justify-between">
                                      <span className="font-medium text-foreground">{ev.entity_title}</span>
                                      <span className="text-[10px] text-muted-foreground uppercase font-mono">
                                        {ev.entity_type}
                                      </span>
                                    </div>
                                    <p className="text-muted-foreground">{ev.evidence_snippet}</p>
                                    {ev.confidence_or_metric && (
                                      <p className="text-[10px] text-primary">
                                        Metric/Confidence: {ev.confidence_or_metric}
                                      </p>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}

                        {/* Suggested Next Steps */}
                        {sr?.suggested_next_steps && sr.suggested_next_steps.length > 0 && (
                          <div className="border-t border-border pt-2">
                            <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                              Suggested Follow-ups
                            </span>
                            <div className="mt-1 flex flex-wrap gap-1.5">
                              {sr.suggested_next_steps.map((step, idx) => (
                                <button
                                  key={idx}
                                  onClick={() => handleSend(step)}
                                  className="rounded-full bg-accent px-2.5 py-1 text-[11px] text-accent-foreground hover:bg-accent/80 transition-colors"
                                >
                                  {step}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Epistemic disclaimer */}
                        {sr?.epistemic_disclaimer && (
                          <p className="text-[10px] text-muted-foreground italic border-t border-border pt-2">
                            {sr.epistemic_disclaimer}
                          </p>
                        )}
                      </>
                    )}
                  </div>

                  {isUser && (
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground mt-0.5">
                      <User className="h-3.5 w-3.5" />
                    </div>
                  )}
                </div>
              );
            })
          )}

          {isLoading && (
            <div className="flex gap-3">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Bot className="h-3.5 w-3.5 animate-spin" />
              </div>
              <div className="rounded-2xl rounded-tl-none border border-border bg-background p-3.5 text-xs text-muted-foreground flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-primary animate-ping" />
                <span>Retrieving user records and validating evidence...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Query Input Bar */}
        <div className="border-t border-border p-3.5">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask about your tasks, projects, blockers, focus windows, or monthly trends..."
              className="flex-1 rounded-lg border border-border bg-background px-3.5 py-2 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              className="inline-flex items-center justify-center rounded-lg bg-primary px-3.5 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              <Send className="h-3.5 w-3.5" />
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
