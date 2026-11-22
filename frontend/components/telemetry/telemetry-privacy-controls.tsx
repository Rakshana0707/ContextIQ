"use client";

import Link from "next/link";
import {
  ShieldCheck,
  PauseCircle,
  PlayCircle,
  Clock,
  ArrowRight,
  EyeOff,
  Sliders,
  CheckCircle2,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface TelemetryPrivacyControlsProps {
  isPaused: boolean;
  onPause: (minutes?: number) => void;
  onResume: () => void;
  loading?: boolean;
}

export function TelemetryPrivacyControls({
  isPaused,
  onPause,
  onResume,
  loading,
}: TelemetryPrivacyControlsProps) {
  return (
    <Card className="border border-border/80 shadow-xs">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <CardTitle className="text-base font-semibold">Privacy & Agency Controls</CardTitle>
              <CardDescription className="text-xs">
                Zero-keystroke logging • User-controlled pause & app exclusions
              </CardDescription>
            </div>
          </div>

          <Link href="/privacy">
            <Button variant="ghost" size="sm" className="text-xs h-7 text-muted-foreground hover:text-foreground">
              Privacy Cockpit
              <ArrowRight className="h-3.5 w-3.5 ml-1" />
            </Button>
          </Link>
        </div>
      </CardHeader>

      <CardContent className="space-y-3.5">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 rounded-lg bg-muted/30 border border-border/60">
          <div className="space-y-0.5">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-foreground">
                Quick Pause Telemetry
              </span>
              {isPaused ? (
                <Badge variant="outline" className="text-[10px] bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400 border-amber-300">
                  Paused
                </Badge>
              ) : (
                <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border-emerald-300">
                  Active
                </Badge>
              )}
            </div>
            <p className="text-[11px] text-muted-foreground">
              Temporarily suspend all window focus and idle collection during confidential tasks.
            </p>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {isPaused ? (
              <Button
                variant="default"
                size="sm"
                className="h-7 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                onClick={onResume}
                disabled={loading}
              >
                <PlayCircle className="h-3.5 w-3.5 mr-1" />
                Resume Now
              </Button>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs px-2"
                  onClick={() => onPause(15)}
                  disabled={loading}
                >
                  15m
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs px-2"
                  onClick={() => onPause(60)}
                  disabled={loading}
                >
                  1h
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs px-2"
                  onClick={() => onPause(240)}
                  disabled={loading}
                >
                  4h
                </Button>
              </>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-[11px] text-muted-foreground">
          <div className="flex items-center gap-2 p-2 rounded-md bg-muted/20 border border-border/40">
            <EyeOff className="h-4 w-4 text-primary shrink-0" />
            <span>Title sanitization & path filtering active</span>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-md bg-muted/20 border border-border/40">
            <Sliders className="h-4 w-4 text-primary shrink-0" />
            <span>Exclusion rules applied pre-upload</span>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-md bg-muted/20 border border-border/40">
            <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
            <span>AES-256 local buffering enabled</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
