"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  KnowledgeNode,
  KnowledgeRelationship,
  GraphOverview,
  GraphNodeType,
  GraphRelationshipType,
  KnowledgeEvidence,
} from "@/types/knowledge_graph";
import { knowledgeGraphApi } from "@/lib/api/services/knowledge_graph";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Search,
  Filter,
  RefreshCw,
  Sparkles,
  Layers,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Minimize2,
  Info,
  ShieldCheck,
  AlertTriangle,
  ArrowRight,
  GitFork,
  Trash2,
  CheckCircle2,
  Brain,
  Calendar,
  CheckSquare,
  Target,
  Flame,
  FileText,
  Activity,
  Award,
  ChevronRight,
  ExternalLink,
} from "lucide-react";

// Color palettes for Node Types
const NODE_TYPE_COLORS: Record<GraphNodeType, { bg: string; border: string; text: string; dot: string }> = {
  USER: { bg: "bg-slate-500/10", border: "border-slate-500/40", text: "text-slate-400", dot: "#94a3b8" },
  TASK: { bg: "bg-blue-500/10", border: "border-blue-500/40", text: "text-blue-400", dot: "#3b82f6" },
  PROJECT: { bg: "bg-indigo-500/10", border: "border-indigo-500/40", text: "text-indigo-400", dot: "#6366f1" },
  GOAL: { bg: "bg-amber-500/10", border: "border-amber-500/40", text: "text-amber-400", dot: "#f59e0b" },
  MILESTONE: { bg: "bg-orange-500/10", border: "border-orange-500/40", text: "text-orange-400", dot: "#f97316" },
  HABIT: { bg: "bg-emerald-500/10", border: "border-emerald-500/40", text: "text-emerald-400", dot: "#10b981" },
  BEHAVIORAL_PATTERN: { bg: "bg-purple-500/10", border: "border-purple-500/40", text: "text-purple-400", dot: "#a855f7" },
  CONTEXT: { bg: "bg-teal-500/10", border: "border-teal-500/40", text: "text-teal-400", dot: "#14b8a6" },
  INTERRUPTION: { bg: "bg-rose-500/10", border: "border-rose-500/40", text: "text-rose-400", dot: "#f43f5e" },
  RECOMMENDATION: { bg: "bg-yellow-500/10", border: "border-yellow-500/40", text: "text-yellow-400", dot: "#eab308" },
  DECISION: { bg: "bg-emerald-500/10", border: "border-emerald-500/40", text: "text-emerald-400", dot: "#10b981" },
  CALENDAR_EVENT: { bg: "bg-violet-500/10", border: "border-violet-500/40", text: "text-violet-400", dot: "#8b5cf6" },
  WORKFLOW: { bg: "bg-cyan-500/10", border: "border-cyan-500/40", text: "text-cyan-400", dot: "#06b6d4" },
  OUTCOME: { bg: "bg-green-500/10", border: "border-green-500/40", text: "text-green-400", dot: "#22c55e" },
  RESOURCE: { bg: "bg-gray-500/10", border: "border-gray-500/40", text: "text-gray-400", dot: "#6b7280" },
};

export function KnowledgeGraphExplorer() {
  const [nodes, setNodes] = useState<KnowledgeNode[]>([]);
  const [relationships, setRelationships] = useState<KnowledgeRelationship[]>([]);
  const [overview, setOverview] = useState<GraphOverview | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [autoPopulating, setAutoPopulating] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedNodeType, setSelectedNodeType] = useState<string>("ALL");
  const [showInferredOnly, setShowInferredOnly] = useState<boolean>(false);
  const [selectedNode, setSelectedNode] = useState<KnowledgeNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<KnowledgeRelationship | null>(null);
  const [evidenceList, setEvidenceList] = useState<KnowledgeEvidence[]>([]);
  const [focusNeighborhood, setFocusNeighborhood] = useState<boolean>(false);
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isDraggingCanvas, setIsDraggingCanvas] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Initial load
  const loadGraph = async () => {
    setLoading(true);
    try {
      const [ovData, nodesData, relsData] = await Promise.all([
        knowledgeGraphApi.getOverview(),
        knowledgeGraphApi.getNodes({ limit: 100 }),
        knowledgeGraphApi.getRelationships({ limit: 150 }),
      ]);
      setOverview(ovData);
      setNodes(nodesData);
      setRelationships(relsData);
    } catch (err) {
      console.error("Failed to load knowledge graph data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGraph();
  }, []);

  // Handle Edge Selection & Fetch Evidence
  useEffect(() => {
    if (selectedEdge) {
      knowledgeGraphApi.getEvidence(selectedEdge.id).then((evs) => {
        setEvidenceList(evs);
      }).catch(() => setEvidenceList([]));
    } else {
      setEvidenceList([]);
    }
  }, [selectedEdge]);

  // Auto-populate trigger
  const handleAutoPopulate = async () => {
    setAutoPopulating(true);
    try {
      await knowledgeGraphApi.autoPopulate();
      await loadGraph();
    } catch (err) {
      console.error("Failed to auto-populate graph", err);
    } finally {
      setAutoPopulating(false);
    }
  };

  // Remove Inferred Relationship
  const handleRemoveInferred = async (relId: string) => {
    if (!confirm("Are you sure you want to remove this inferred relationship?")) return;
    try {
      await knowledgeGraphApi.removeInferredRelationship(relId);
      setSelectedEdge(null);
      await loadGraph();
    } catch (err) {
      console.error("Failed to remove inferred relationship", err);
    }
  };

  // Filtered nodes
  const filteredNodes = useMemo(() => {
    return nodes.filter((node) => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = node.name.toLowerCase().includes(q);
        const matchesType = node.node_type.toLowerCase().includes(q);
        if (!matchesName && !matchesType) return false;
      }
      if (selectedNodeType !== "ALL" && node.node_type !== selectedNodeType) {
        return false;
      }
      if (focusNeighborhood && selectedNode) {
        if (node.id === selectedNode.id) return true;
        const isNeighbor = relationships.some(
          (r) =>
            (r.source_node_id === selectedNode.id && r.target_node_id === node.id) ||
            (r.target_node_id === selectedNode.id && r.source_node_id === node.id)
        );
        return isNeighbor;
      }
      return true;
    });
  }, [nodes, searchQuery, selectedNodeType, focusNeighborhood, selectedNode, relationships]);

  const visibleNodeIds = useMemo(() => new Set(filteredNodes.map((n) => n.id)), [filteredNodes]);

  // Filtered relationships
  const filteredRelationships = useMemo(() => {
    return relationships.filter((rel) => {
      if (!visibleNodeIds.has(rel.source_node_id) || !visibleNodeIds.has(rel.target_node_id)) {
        return false;
      }
      if (showInferredOnly && !rel.is_inferred) {
        return false;
      }
      return true;
    });
  }, [relationships, visibleNodeIds, showInferredOnly]);

  // Compute Layout Coordinates (Radial Force Simulation Simulation)
  const nodePositions = useMemo(() => {
    const posMap: Record<string, { x: number; y: number }> = {};
    const count = filteredNodes.length;
    if (count === 0) return posMap;

    const centerX = 450;
    const centerY = 320;
    const radius = Math.min(260, Math.max(140, count * 24));

    filteredNodes.forEach((node, idx) => {
      const angle = (idx / count) * 2 * Math.PI;
      // Stagger odd/even for visual depth
      const rOffset = idx % 2 === 0 ? 0 : 40;
      posMap[node.id] = {
        x: centerX + (radius + rOffset) * Math.cos(angle),
        y: centerY + (radius + rOffset) * Math.sin(angle),
      };
    });
    return posMap;
  }, [filteredNodes]);

  // Zoom / Pan handlers
  const handleZoom = (delta: number) => {
    setZoom((prev) => Math.min(2.5, Math.max(0.4, prev + delta)));
  };

  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setSelectedNode(null);
    setSelectedEdge(null);
    setFocusNeighborhood(false);
  };

  const handleMouseDownCanvas = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget || (e.target as HTMLElement).tagName === "svg") {
      setIsDraggingCanvas(true);
      setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMoveCanvas = (e: React.MouseEvent) => {
    if (isDraggingCanvas) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };

  const handleMouseUpCanvas = () => {
    setIsDraggingCanvas(false);
  };

  return (
    <div className="flex flex-col gap-5 h-full">
      {/* Overview Metric Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <Card className="bg-card/70 border-border/80 p-3">
          <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-indigo-500" />
            Total Nodes
          </div>
          <div className="text-xl font-extrabold text-foreground mt-1">{overview?.total_nodes ?? nodes.length}</div>
          <div className="text-[10px] text-muted-foreground/80 mt-0.5">Across 15 entity types</div>
        </Card>

        <Card className="bg-card/70 border-border/80 p-3">
          <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <GitFork className="h-3.5 w-3.5 text-blue-500" />
            Relationships
          </div>
          <div className="text-xl font-extrabold text-foreground mt-1">{overview?.total_relationships ?? relationships.length}</div>
          <div className="text-[10px] text-muted-foreground/80 mt-0.5">Verified & Inferred</div>
        </Card>

        <Card className="bg-card/70 border-border/80 p-3">
          <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
            Explicit Facts
          </div>
          <div className="text-xl font-extrabold text-emerald-500 mt-1">{overview?.explicit_relationship_count ?? 0}</div>
          <div className="text-[10px] text-muted-foreground/80 mt-0.5">Confidence = 100%</div>
        </Card>

        <Card className="bg-card/70 border-border/80 p-3">
          <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-purple-500" />
            Inferred Edges
          </div>
          <div className="text-xl font-extrabold text-purple-400 mt-1">{overview?.inferred_relationship_count ?? 0}</div>
          <div className="text-[10px] text-muted-foreground/80 mt-0.5">Evidence Grounded</div>
        </Card>

        <Card className="bg-card/70 border-border/80 p-3">
          <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
            <Activity className="h-3.5 w-3.5 text-amber-500" />
            Graph Version
          </div>
          <div className="text-xl font-extrabold text-foreground mt-1">v{overview?.current_version ?? 1}</div>
          <div className="text-[10px] text-muted-foreground/80 mt-0.5">Incremental state audit</div>
        </Card>

        <Card className="bg-card/70 border-border/80 p-3 flex flex-col justify-between">
          <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">Sync State</div>
          <Button
            size="sm"
            variant="outline"
            onClick={handleAutoPopulate}
            disabled={autoPopulating}
            className="w-full text-xs font-semibold h-7 border-indigo-500/30 text-indigo-400 hover:bg-indigo-500/10"
          >
            <RefreshCw className={`h-3 w-3 mr-1.5 ${autoPopulating ? "animate-spin" : ""}`} />
            {autoPopulating ? "Populating..." : "Auto-Populate"}
          </Button>
        </Card>
      </div>

      {/* Control Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-card/60 border border-border/70 p-3 rounded-xl backdrop-blur-md">
        <div className="flex items-center gap-3 flex-1 min-w-[280px]">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              placeholder="Search nodes by title or entity..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 h-8 text-xs bg-muted/40 border-border/80"
            />
          </div>

          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Filter className="h-3.5 w-3.5" />
            <select
              value={selectedNodeType}
              onChange={(e) => setSelectedNodeType(e.target.value)}
              aria-label="Filter by node type"
              className="bg-muted/40 border border-border/80 rounded-md px-2 py-1 text-xs text-foreground focus:outline-hidden"
            >
              <option value="ALL">All Entity Types</option>
              <option value="TASK">Tasks</option>
              <option value="PROJECT">Projects</option>
              <option value="GOAL">Goals</option>
              <option value="BEHAVIORAL_PATTERN">Behavioral Patterns</option>
              <option value="CALENDAR_EVENT">Calendar Events</option>
              <option value="RECOMMENDATION">Recommendations</option>
              <option value="DECISION">Decisions</option>
              <option value="OUTCOME">Outcomes</option>
            </select>
          </div>

          <Button
            size="sm"
            variant={showInferredOnly ? "default" : "outline"}
            onClick={() => setShowInferredOnly(!showInferredOnly)}
            className="h-8 text-xs font-semibold px-2.5"
          >
            <Sparkles className="h-3 w-3 mr-1.5" />
            {showInferredOnly ? "Inferred Only" : "All Edges"}
          </Button>
        </div>

        {/* Canvas Navigation Tools */}
        <div className="flex items-center gap-1.5">
          <Button size="icon" variant="outline" className="h-8 w-8" onClick={() => handleZoom(0.15)} title="Zoom In">
            <ZoomIn className="h-3.5 w-3.5" />
          </Button>
          <Button size="icon" variant="outline" className="h-8 w-8" onClick={() => handleZoom(-0.15)} title="Zoom Out">
            <ZoomOut className="h-3.5 w-3.5" />
          </Button>
          <Button size="icon" variant="outline" className="h-8 w-8" onClick={handleResetView} title="Reset Canvas">
            <Maximize2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Main Interactive Canvas & Details Inspector Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1 min-h-[580px]">
        {/* SVG Canvas Area */}
        <div
          className="lg:col-span-8 bg-card/40 border border-border/80 rounded-2xl relative overflow-hidden flex items-center justify-center cursor-grab active:cursor-grabbing select-none"
          onMouseDown={handleMouseDownCanvas}
          onMouseMove={handleMouseMoveCanvas}
          onMouseUp={handleMouseUpCanvas}
        >
          {loading && (
            <div className="absolute inset-0 bg-background/60 backdrop-blur-xs flex items-center justify-center z-20">
              <RefreshCw className="h-6 w-6 animate-spin text-indigo-500" />
            </div>
          )}

          <svg
            className="w-full h-full min-h-[580px]"
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: "center center",
              transition: isDraggingCanvas ? "none" : "transform 0.15s ease-out",
            }}
          >
            <defs>
              <marker
                id="arrowhead-fact"
                markerWidth="8"
                markerHeight="6"
                refX="22"
                refY="3"
                orient="auto"
              >
                <polygon points="0 0, 8 3, 0 6" fill="#6366f1" opacity="0.8" />
              </marker>
              <marker
                id="arrowhead-inferred"
                markerWidth="8"
                markerHeight="6"
                refX="22"
                refY="3"
                orient="auto"
              >
                <polygon points="0 0, 8 3, 0 6" fill="#a855f7" opacity="0.8" />
              </marker>
            </defs>

            {/* Render Relationship Edges */}
            {filteredRelationships.map((rel) => {
              const srcPos = nodePositions[rel.source_node_id];
              const tgtPos = nodePositions[rel.target_node_id];
              if (!srcPos || !tgtPos) return null;

              const isSelected = selectedEdge?.id === rel.id;
              const isConnectedToSelectedNode =
                selectedNode &&
                (rel.source_node_id === selectedNode.id || rel.target_node_id === selectedNode.id);

              const strokeColor = rel.is_inferred ? "#a855f7" : "#6366f1";
              const strokeWidth = isSelected ? 3 : isConnectedToSelectedNode ? 2.2 : 1.4;
              const strokeDash = rel.is_inferred ? "4 3" : undefined;
              const marker = rel.is_inferred ? "url(#arrowhead-inferred)" : "url(#arrowhead-fact)";

              const midX = (srcPos.x + tgtPos.x) / 2;
              const midY = (srcPos.y + tgtPos.y) / 2;

              return (
                <g key={rel.id} className="cursor-pointer group" onClick={() => setSelectedEdge(rel)}>
                  <line
                    x1={srcPos.x}
                    y1={srcPos.y}
                    x2={tgtPos.x}
                    y2={tgtPos.y}
                    stroke={strokeColor}
                    strokeWidth={strokeWidth}
                    strokeDasharray={strokeDash}
                    markerEnd={marker}
                    opacity={isSelected || isConnectedToSelectedNode ? 0.95 : 0.45}
                    className="transition-all duration-200"
                  />
                  {/* Edge Label Badge */}
                  <rect
                    x={midX - 34}
                    y={midY - 9}
                    width={68}
                    height={18}
                    rx={9}
                    fill="#0f172a"
                    stroke={strokeColor}
                    strokeWidth={isSelected ? 1.5 : 0.8}
                    opacity={0.88}
                  />
                  <text
                    x={midX}
                    y={midY + 3.5}
                    textAnchor="middle"
                    fill={rel.is_inferred ? "#d8b4fe" : "#a5b4fc"}
                    fontSize="8"
                    fontWeight="700"
                    className="select-none pointer-events-none"
                  >
                    {rel.relationship_type.substring(0, 10)}
                  </text>
                </g>
              );
            })}

            {/* Render Nodes */}
            {filteredNodes.map((node) => {
              const pos = nodePositions[node.id];
              if (!pos) return null;

              const isSelected = selectedNode?.id === node.id;
              const style = NODE_TYPE_COLORS[node.node_type] || NODE_TYPE_COLORS.TASK;

              return (
                <g
                  key={node.id}
                  transform={`translate(${pos.x}, ${pos.y})`}
                  className="cursor-pointer group"
                  onClick={() => {
                    setSelectedNode(node);
                    setSelectedEdge(null);
                  }}
                >
                  {/* Outer Pulsing Glow on Selection */}
                  {isSelected && (
                    <circle r={28} fill={style.dot} opacity={0.2} className="animate-pulse" />
                  )}

                  {/* Core Node Circle */}
                  <circle
                    r={isSelected ? 20 : 16}
                    fill="#0f172a"
                    stroke={style.dot}
                    strokeWidth={isSelected ? 2.8 : 1.8}
                    className="transition-all duration-200 group-hover:scale-110"
                  />

                  {/* Inner Node Identifier Icon / Dot */}
                  <circle r={isSelected ? 6 : 4.5} fill={style.dot} />

                  {/* Label Text */}
                  <text
                    y={28}
                    textAnchor="middle"
                    fill="#f1f5f9"
                    fontSize={isSelected ? "11" : "10"}
                    fontWeight={isSelected ? "700" : "500"}
                    className="select-none pointer-events-none drop-shadow-md"
                  >
                    {node.name.length > 20 ? `${node.name.substring(0, 18)}...` : node.name}
                  </text>
                </g>
              );
            })}
          </svg>

          {/* Canvas Bottom Overlay Indicators */}
          <div className="absolute bottom-3 left-3 bg-background/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-border/70 text-[10px] text-muted-foreground flex items-center gap-3">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-indigo-500 inline-block" />
              Solid Line: Verified Fact
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-purple-500 inline-block" />
              Dashed Line: Inferred Hypothesis
            </span>
            <span>Zoom: {Math.round(zoom * 100)}%</span>
          </div>
        </div>

        {/* Right Details & Evidence Inspector Drawer */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          {/* Node Inspector */}
          {selectedNode ? (
            <Card className="bg-card/70 border-border/80 h-full flex flex-col">
              <CardHeader className="p-4 border-b border-border/70">
                <div className="flex items-center justify-between gap-2">
                  <Badge variant="outline" className={`${NODE_TYPE_COLORS[selectedNode.node_type].bg} ${NODE_TYPE_COLORS[selectedNode.node_type].text} border-current`}>
                    {selectedNode.node_type}
                  </Badge>
                  <Button
                    size="sm"
                    variant={focusNeighborhood ? "default" : "outline"}
                    className="h-7 text-xs font-semibold px-2"
                    onClick={() => setFocusNeighborhood(!focusNeighborhood)}
                  >
                    {focusNeighborhood ? "Show Full Graph" : "Focus Neighborhood"}
                  </Button>
                </div>
                <CardTitle className="text-base font-extrabold text-foreground mt-2 leading-tight">
                  {selectedNode.name}
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Entity Table: <span className="font-mono">{selectedNode.entity_table}</span>
                </CardDescription>
              </CardHeader>

              <CardContent className="p-4 space-y-4 flex-1 overflow-y-auto">
                {/* Properties Overview */}
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/80 mb-1.5">
                    Node Attributes
                  </div>
                  <div className="bg-muted/40 rounded-lg p-2.5 space-y-1.5 text-xs">
                    {Object.entries(selectedNode.properties || {}).map(([k, v]) => (
                      <div key={k} className="flex justify-between items-center gap-2">
                        <span className="text-muted-foreground font-medium">{k}:</span>
                        <span className="font-mono text-foreground truncate max-w-[160px]">
                          {typeof v === "object" ? JSON.stringify(v) : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Connected Relationships */}
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/80 mb-1.5">
                    Connected Relationships
                  </div>
                  <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                    {relationships
                      .filter((r) => r.source_node_id === selectedNode.id || r.target_node_id === selectedNode.id)
                      .map((r) => {
                        const isSource = r.source_node_id === selectedNode.id;
                        const otherNodeId = isSource ? r.target_node_id : r.source_node_id;
                        const otherNode = nodes.find((n) => n.id === otherNodeId);

                        return (
                          <div
                            key={r.id}
                            onClick={() => setSelectedEdge(r)}
                            className="p-2 rounded-lg bg-muted/30 hover:bg-muted/60 border border-border/60 cursor-pointer transition-colors text-xs flex items-center justify-between"
                          >
                            <div className="flex items-center gap-2 truncate">
                              <Badge variant="outline" className="text-[9px] px-1.5 py-0 h-4">
                                {r.relationship_type}
                              </Badge>
                              <span className="truncate text-foreground/90 font-medium">
                                {otherNode?.name || otherNodeId}
                              </span>
                            </div>
                            <span className="text-[10px] text-muted-foreground shrink-0 font-mono">
                              {r.is_inferred ? `${Math.round(r.confidence * 100)}%` : "FACT"}
                            </span>
                          </div>
                        );
                      })}
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : selectedEdge ? (
            /* Relationship & Evidence Inspector */
            <Card className="bg-card/70 border-border/80 h-full flex flex-col">
              <CardHeader className="p-4 border-b border-border/70">
                <div className="flex items-center justify-between gap-2">
                  <Badge
                    variant="outline"
                    className={
                      selectedEdge.is_inferred
                        ? "bg-purple-500/10 text-purple-400 border-purple-500/30"
                        : "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                    }
                  >
                    {selectedEdge.is_inferred ? "INFERRED HYPOTHESIS" : "VERIFIED FACT"}
                  </Badge>
                  {selectedEdge.is_inferred && (
                    <Button
                      size="sm"
                      variant="destructive"
                      className="h-7 text-xs font-semibold px-2"
                      onClick={() => handleRemoveInferred(selectedEdge.id)}
                    >
                      <Trash2 className="h-3 w-3 mr-1" />
                      Remove
                    </Button>
                  )}
                </div>
                <CardTitle className="text-base font-extrabold text-foreground mt-2 leading-tight flex items-center gap-2">
                  <span>{selectedEdge.relationship_type}</span>
                </CardTitle>
                <CardDescription className="text-xs text-muted-foreground">
                  Evidence Source: <span className="font-semibold text-foreground">{selectedEdge.evidence_source}</span>
                </CardDescription>
              </CardHeader>

              <CardContent className="p-4 space-y-4 flex-1 overflow-y-auto">
                {/* Confidence Meter */}
                <div>
                  <div className="flex justify-between items-center text-xs mb-1">
                    <span className="text-muted-foreground font-medium">Calibrated Confidence</span>
                    <span className="font-bold text-foreground font-mono">
                      {Math.round(selectedEdge.confidence * 100)}%
                    </span>
                  </div>
                  <div className="w-full bg-muted/60 rounded-full h-2 overflow-hidden">
                    <div
                      className={`h-full ${
                        selectedEdge.is_inferred ? "bg-purple-500" : "bg-emerald-500"
                      }`}
                      style={{ width: `${selectedEdge.confidence * 100}%` }}
                    />
                  </div>
                </div>

                {/* Evidence Attachments */}
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/80 mb-1.5 flex items-center justify-between">
                    <span>Attached Evidence Records ({evidenceList.length})</span>
                    <ShieldCheck className="h-3 w-3 text-emerald-400" />
                  </div>

                  {evidenceList.length > 0 ? (
                    <div className="space-y-2">
                      {evidenceList.map((ev) => (
                        <div key={ev.id} className="p-2.5 rounded-lg bg-muted/40 border border-border/70 text-xs space-y-1">
                          <div className="flex justify-between items-center">
                            <span className="font-bold text-foreground">{ev.evidence_type}</span>
                            <span className="text-[10px] text-muted-foreground font-mono">
                              {Math.round(ev.confidence_score * 100)}% confidence
                            </span>
                          </div>
                          {ev.source_entity_table && (
                            <div className="text-[10px] text-muted-foreground">
                              Origin: <span className="font-mono">{ev.source_entity_table}</span>
                            </div>
                          )}
                          <pre className="text-[9px] bg-background/60 p-1.5 rounded-md font-mono text-muted-foreground overflow-x-auto">
                            {JSON.stringify(ev.payload, null, 2)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-3 rounded-lg bg-muted/20 border border-border/60 text-xs text-muted-foreground text-center">
                      Ground truth edge backed by user interaction.
                    </div>
                  )}
                </div>

                {/* Provenance Metadata Payload */}
                {selectedEdge.provenance_payload && Object.keys(selectedEdge.provenance_payload).length > 0 && (
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground/80 mb-1.5">
                      Provenance Payload
                    </div>
                    <pre className="text-[10px] bg-muted/40 p-2.5 rounded-lg font-mono text-muted-foreground overflow-x-auto">
                      {JSON.stringify(selectedEdge.provenance_payload, null, 2)}
                    </pre>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : (
            /* Default Selection Prompt */
            <Card className="bg-card/70 border-border/80 h-full flex flex-col items-center justify-center p-6 text-center">
              <GitFork className="h-10 w-10 text-muted-foreground/40 mb-3" />
              <div className="text-sm font-bold text-foreground">Select an Entity or Edge</div>
              <p className="text-xs text-muted-foreground max-w-xs mt-1">
                Click on any node in the knowledge graph to inspect properties, neighborhood connections, or click an edge to inspect empirical evidence trails.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
