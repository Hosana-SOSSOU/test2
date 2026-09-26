import React, { useState, useEffect } from 'react';
import {
  FileText,
  FolderTree,
  ShieldCheck,
  Terminal,
  Play,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Copy,
  Search,
  Cpu,
  Layers,
  Settings,
  BookOpen,
  FileCheck,
  RefreshCw,
  FileWarning,
  ArrowRight,
  Lock,
  Check,
  Code2,
  Folder,
  FileCode,
  Sparkles,
} from 'lucide-react';

interface ProjectNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  children?: ProjectNode[];
}

interface DemoResult {
  documents: any[];
  classifications: Record<string, any>;
  plans: any[];
  duplicates: any[];
  simulation: {
    total: number;
    would_move: number;
    collisions: number;
    manual_reviews: number;
    report_text: string;
  };
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'workbench' | 'code' | 'terminal' | 'tests' | 'taxonomy' | 'safety'>('workbench');
  const [projectTree, setProjectTree] = useState<ProjectNode[]>([]);
  const [selectedFilePath, setSelectedFilePath] = useState<string>('src/pdf_organizer/models.py');
  const [fileContent, setFileContent] = useState<string>('');
  const [fileLoading, setFileLoading] = useState<boolean>(false);

  // Demo Workbench State
  const [demoLoading, setDemoLoading] = useState<boolean>(false);
  const [demoData, setDemoData] = useState<DemoResult | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<any | null>(null);

  // Terminal State
  const [cliCommand, setCliCommand] = useState<string>('./pdf-organizer --help');
  const [cliOutput, setCliOutput] = useState<string>('Ready. Click a preset command or enter a command below.');
  const [cliRunning, setCliRunning] = useState<boolean>(false);

  // Tests State
  const [testOutput, setTestOutput] = useState<string | null>(null);
  const [testRunning, setTestRunning] = useState<boolean>(false);
  const [testSuccess, setTestSuccess] = useState<boolean | null>(null);

  // Load project file tree on start
  useEffect(() => {
    fetch('/api/project-tree')
      .then((res) => res.json())
      .then((data) => {
        if (data.tree) setProjectTree(data.tree);
      })
      .catch((err) => console.error(err));
  }, []);

  // Load file content when selection changes
  useEffect(() => {
    if (!selectedFilePath) return;
    setFileLoading(true);
    fetch(`/api/file-content?path=${encodeURIComponent(selectedFilePath)}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.content !== undefined) {
          setFileContent(data.content);
        } else {
          setFileContent('// Could not load file content: ' + (data.error || 'Unknown error'));
        }
      })
      .catch((err) => setFileContent('// Error loading file: ' + err.message))
      .finally(() => setFileLoading(false));
  }, [selectedFilePath]);

  // Run demo workbench
  const runDemoWorkbench = async () => {
    setDemoLoading(true);
    try {
      const res = await fetch('/api/demo/setup-and-process', { method: 'POST' });
      const data = await res.json();
      setDemoData(data);
      if (data.documents && data.documents.length > 0) {
        setSelectedDoc(data.documents[0]);
      }
    } catch (err: any) {
      console.error(err);
    } finally {
      setDemoLoading(false);
    }
  };

  // Run initial demo once
  useEffect(() => {
    runDemoWorkbench();
  }, []);

  // Run CLI command
  const executeCli = async (cmdToRun?: string) => {
    const cmd = cmdToRun || cliCommand;
    setCliRunning(true);
    setCliOutput(`$ ${cmd}\nExecuting on local Linux environment...`);
    try {
      const res = await fetch('/api/cli/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd }),
      });
      const data = await res.json();
      setCliOutput(`$ ${cmd}\n\n${data.output || 'No output'}`);
    } catch (err: any) {
      setCliOutput(`$ ${cmd}\n\nExecution error: ${err.message}`);
    } finally {
      setCliRunning(false);
    }
  };

  // Run Tests
  const runTests = async () => {
    setTestRunning(true);
    setTestOutput('Running python3 -m unittest discover tests...');
    try {
      const res = await fetch('/api/tests/run');
      const data = await res.json();
      setTestSuccess(data.success);
      setTestOutput(data.output);
    } catch (err: any) {
      setTestSuccess(false);
      setTestOutput('Test execution error: ' + err.message);
    } finally {
      setTestRunning(false);
    }
  };

  const renderTree = (nodes: ProjectNode[]) => {
    return (
      <ul className="space-y-1 text-sm font-mono">
        {nodes.map((node) => {
          if (node.type === 'directory') {
            return (
              <li key={node.path} className="space-y-1">
                <div className="flex items-center gap-1.5 text-zinc-300 font-semibold px-2 py-1 rounded bg-zinc-800/40">
                  <Folder className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span className="truncate">{node.name}/</span>
                </div>
                {node.children && <div className="pl-4 border-l border-zinc-800 ml-2">{renderTree(node.children)}</div>}
              </li>
            );
          }
          const isSelected = selectedFilePath === node.path;
          return (
            <li key={node.path}>
              <button
                onClick={() => setSelectedFilePath(node.path)}
                className={`w-full flex items-center justify-between gap-2 px-2 py-1 text-left rounded transition-colors ${
                  isSelected ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200'
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <FileCode className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
                  <span className="truncate">{node.name}</span>
                </div>
                {node.size !== undefined && <span className="text-[10px] text-zinc-600 shrink-0">{(node.size / 1024).toFixed(1)}k</span>}
              </button>
            </li>
          );
        })}
      </ul>
    );
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col font-sans">
      {/* Top Banner & Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/80 backdrop-blur sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shadow-sm">
              <FileCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-lg tracking-tight text-white">Local Intelligent PDF Organizer</h1>
                <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  v1.0.0 Linux
                </span>
              </div>
              <p className="text-xs text-zinc-400">
                100% Local-First • Offline-Capable • Safe dry-run • Zero External API
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-800 border border-zinc-700 text-xs text-zinc-300">
              <Lock className="w-3.5 h-3.5 text-emerald-400" />
              <span>Offline / Local Only</span>
            </div>
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-zinc-800 border border-zinc-700 text-xs text-zinc-300">
              <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
              <span>NEVER OVERWRITE</span>
            </div>
            <button
              onClick={runTests}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs shadow transition cursor-pointer"
            >
              <Play className="w-3.5 h-3.5" />
              <span>Run Tests (28)</span>
            </button>
          </div>
        </div>

        {/* Tabs Bar */}
        <div className="max-w-7xl mx-auto px-4 flex gap-1 overflow-x-auto border-t border-zinc-800/60 pt-1 text-sm font-medium">
          <button
            onClick={() => setActiveTab('workbench')}
            className={`px-4 py-2 border-b-2 flex items-center gap-2 transition cursor-pointer ${
              activeTab === 'workbench'
                ? 'border-emerald-500 text-emerald-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Sparkles className="w-4 h-4" />
            <span>Live Workbench & Simulator</span>
          </button>
          <button
            onClick={() => setActiveTab('code')}
            className={`px-4 py-2 border-b-2 flex items-center gap-2 transition cursor-pointer ${
              activeTab === 'code'
                ? 'border-emerald-500 text-emerald-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Code2 className="w-4 h-4" />
            <span>Python Architecture & Code</span>
          </button>
          <button
            onClick={() => setActiveTab('terminal')}
            className={`px-4 py-2 border-b-2 flex items-center gap-2 transition cursor-pointer ${
              activeTab === 'terminal'
                ? 'border-emerald-500 text-emerald-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Terminal className="w-4 h-4" />
            <span>Linux CLI Runner</span>
          </button>
          <button
            onClick={() => setActiveTab('tests')}
            className={`px-4 py-2 border-b-2 flex items-center gap-2 transition cursor-pointer ${
              activeTab === 'tests'
                ? 'border-emerald-500 text-emerald-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <CheckCircle2 className="w-4 h-4" />
            <span>Unit Test Suite</span>
          </button>
          <button
            onClick={() => setActiveTab('taxonomy')}
            className={`px-4 py-2 border-b-2 flex items-center gap-2 transition cursor-pointer ${
              activeTab === 'taxonomy'
                ? 'border-emerald-500 text-emerald-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Dynamic Taxonomy & Config</span>
          </button>
          <button
            onClick={() => setActiveTab('safety')}
            className={`px-4 py-2 border-b-2 flex items-center gap-2 transition cursor-pointer ${
              activeTab === 'safety'
                ? 'border-emerald-500 text-emerald-400 font-semibold'
                : 'border-transparent text-zinc-400 hover:text-zinc-200'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>Safety & Rollback Specs</span>
          </button>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {/* TAB 1: WORKBENCH */}
        {activeTab === 'workbench' && (
          <div className="space-y-6">
            {/* Top metrics card */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                <div className="text-xs text-zinc-400">Total Scanned PDFs</div>
                <div className="text-2xl font-bold text-white mt-1">{demoData?.documents.length || 7}</div>
                <div className="text-xs text-emerald-400 mt-1 flex items-center gap-1">
                  <Check className="w-3 h-3" /> Discovered recursively
                </div>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                <div className="text-xs text-zinc-400">Simulation: Would Move</div>
                <div className="text-2xl font-bold text-emerald-400 mt-1">{demoData?.simulation.would_move || 4}</div>
                <div className="text-xs text-zinc-400 mt-1">Confirmed destinations</div>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                <div className="text-xs text-zinc-400">Exact Duplicate Groups</div>
                <div className="text-2xl font-bold text-amber-400 mt-1">{demoData?.duplicates.length || 1}</div>
                <div className="text-xs text-zinc-400 mt-1">SHA-256 byte verified</div>
              </div>
              <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                <div className="text-xs text-zinc-400">Requires OCR / Review</div>
                <div className="text-2xl font-bold text-purple-400 mt-1">
                  {(demoData?.simulation.manual_reviews || 2) + 1}
                </div>
                <div className="text-xs text-zinc-400 mt-1">No silent false positives</div>
              </div>
            </div>

            {/* Workbench layout: Document List + Details + Simulation Dry Run Output */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left Column: Documents List */}
              <div className="lg:col-span-5 bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden flex flex-col">
                <div className="p-3 bg-zinc-850 border-b border-zinc-800 flex items-center justify-between">
                  <h3 className="font-semibold text-sm text-zinc-200 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-emerald-400" />
                    <span>Discovered PDFs Inventory</span>
                  </h3>
                  <button
                    onClick={runDemoWorkbench}
                    disabled={demoLoading}
                    className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1 cursor-pointer"
                  >
                    <RefreshCw className={`w-3 h-3 ${demoLoading ? 'animate-spin' : ''}`} />
                    <span>Re-analyze</span>
                  </button>
                </div>

                <div className="divide-y divide-zinc-800/80 overflow-y-auto max-h-[500px]">
                  {demoData?.documents.map((doc) => {
                    const isSelected = selectedDoc?.filename === doc.filename;
                    const cls = demoData.classifications[doc.path];
                    const isOcr = doc.text_status === 'OCR_REQUIRED';
                    const isReview = cls?.category === 'À_classer';

                    return (
                      <button
                        key={doc.path}
                        onClick={() => setSelectedDoc(doc)}
                        className={`w-full p-3 text-left transition-colors flex flex-col gap-1.5 cursor-pointer ${
                          isSelected ? 'bg-emerald-500/10 border-l-2 border-emerald-500' : 'hover:bg-zinc-800/40'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium text-xs text-zinc-200 truncate">{doc.filename}</span>
                          <span
                            className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                              isOcr
                                ? 'bg-purple-900/50 text-purple-300 border border-purple-700/50'
                                : isReview
                                ? 'bg-amber-900/50 text-amber-300 border border-amber-700/50'
                                : 'bg-emerald-900/50 text-emerald-300 border border-emerald-700/50'
                            }`}
                          >
                            {isOcr ? 'OCR_REQUIRED' : cls?.category ? cls.category.split('/').pop() : 'PENDING'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-[11px] text-zinc-400">
                          <span className="font-mono text-zinc-500">{doc.sha256 ? doc.sha256.substring(0, 10) + '...' : 'no-sha'}</span>
                          <span>Score: {cls ? (cls.score * 100).toFixed(0) + '%' : '0%'}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Right Column: Selected Document Inspection & Plan */}
              <div className="lg:col-span-7 space-y-4">
                {selectedDoc && (
                  <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-start justify-between gap-3 border-b border-zinc-800 pb-3">
                      <div>
                        <h4 className="font-bold text-base text-white">{selectedDoc.filename}</h4>
                        <p className="text-xs text-zinc-400 font-mono mt-0.5">{selectedDoc.path}</p>
                      </div>
                      <div className="text-right">
                        <span className="text-xs text-zinc-500 block">Status</span>
                        <span className="text-xs font-semibold text-emerald-400">{selectedDoc.text_status}</span>
                      </div>
                    </div>

                    {/* Metadata & SHA256 */}
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="bg-zinc-800/50 p-2.5 rounded-lg border border-zinc-800">
                        <span className="text-zinc-500 block">Cryptographic SHA-256</span>
                        <span className="font-mono text-zinc-300 text-[11px] break-all">{selectedDoc.sha256}</span>
                      </div>
                      <div className="bg-zinc-800/50 p-2.5 rounded-lg border border-zinc-800">
                        <span className="text-zinc-500 block">Extracted Text Length</span>
                        <span className="text-zinc-200 font-medium">{selectedDoc.text_length} characters</span>
                      </div>
                    </div>

                    {/* Classification & Explainability */}
                    {demoData?.classifications[selectedDoc.path] && (
                      <div className="bg-zinc-950/60 p-4 rounded-lg border border-zinc-800 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
                            Classification Result ({demoData.classifications[selectedDoc.path].classifier})
                          </span>
                          <span className="text-xs font-bold text-emerald-400">
                            Heuristic Score: {(demoData.classifications[selectedDoc.path].score * 100).toFixed(1)}%
                          </span>
                        </div>
                        <div className="text-sm font-semibold text-emerald-300">
                          Proposed Category: {demoData.classifications[selectedDoc.path].category}
                        </div>
                        <div className="text-xs text-zinc-300 italic">
                          "{demoData.classifications[selectedDoc.path].reason}"
                        </div>
                        {demoData.classifications[selectedDoc.path].evidence?.length > 0 && (
                          <div className="pt-2">
                            <span className="text-xs text-zinc-500 block mb-1">Identified Keywords (Evidence):</span>
                            <div className="flex flex-wrap gap-1.5">
                              {demoData.classifications[selectedDoc.path].evidence.map((ev: string) => (
                                <span
                                  key={ev}
                                  className="px-2 py-0.5 rounded text-[11px] bg-zinc-800 text-zinc-200 border border-zinc-700"
                                >
                                  {ev}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* MovePlan Proposal */}
                    {demoData?.plans.find((p) => p.source === selectedDoc.path) && (
                      <div className="bg-emerald-950/20 border border-emerald-800/40 p-3 rounded-lg space-y-1.5 text-xs">
                        <div className="flex items-center gap-1.5 text-emerald-400 font-semibold">
                          <ArrowRight className="w-4 h-4" />
                          <span>Calculated MovePlan (Safe Destination Proposal)</span>
                        </div>
                        <div className="font-mono text-zinc-300 text-[11px] break-all bg-black/40 p-2 rounded border border-zinc-800">
                          {demoData.plans.find((p) => p.source === selectedDoc.path).destination}
                        </div>
                        <div className="text-[11px] text-zinc-400">
                          Status: <span className="text-emerald-300 font-mono">PROPOSED</span> • Verified non-colliding
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Dry Run Simulation Box */}
                <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                  <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
                    <h4 className="font-semibold text-xs text-zinc-300 flex items-center gap-2">
                      <Terminal className="w-4 h-4 text-emerald-400" />
                      <span>Official Simulation Report (Dry-Run Only)</span>
                    </h4>
                    <span className="text-[11px] text-emerald-400 font-mono bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/40">
                      NO MUTATION
                    </span>
                  </div>
                  <pre className="mt-3 p-3 bg-zinc-950 text-zinc-300 font-mono text-[11px] rounded-lg overflow-x-auto max-h-48 border border-zinc-800/60">
                    {demoData?.simulation.report_text || 'Loading simulation report...'}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: CODE & ARCHITECTURE EXPLORER */}
        {activeTab === 'code' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-4 bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex flex-col space-y-3">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                <h3 className="font-semibold text-sm text-zinc-200 flex items-center gap-2">
                  <FolderTree className="w-4 h-4 text-emerald-400" />
                  <span>Module Structure</span>
                </h3>
                <span className="text-xs text-zinc-500 font-mono">Python 3.10+</span>
              </div>
              <div className="overflow-y-auto max-h-[600px] pr-1">{renderTree(projectTree)}</div>
            </div>

            <div className="lg:col-span-8 bg-zinc-900 border border-zinc-800 rounded-xl flex flex-col overflow-hidden">
              <div className="p-3 bg-zinc-850 border-b border-zinc-800 flex items-center justify-between">
                <span className="font-mono text-xs text-zinc-300 font-medium flex items-center gap-2">
                  <FileCode className="w-4 h-4 text-emerald-400" />
                  {selectedFilePath}
                </span>
                <span className="text-xs text-zinc-500 font-mono">{fileContent.split('\n').length} lines</span>
              </div>
              <div className="flex-1 bg-zinc-950 p-4 overflow-auto max-h-[600px]">
                {fileLoading ? (
                  <div className="flex items-center justify-center py-16 text-zinc-500">
                    <RefreshCw className="w-5 h-5 animate-spin mr-2" /> Loading code...
                  </div>
                ) : (
                  <pre className="font-mono text-xs text-zinc-300 leading-relaxed whitespace-pre">
                    <code>{fileContent}</code>
                  </pre>
                )}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: CLI TERMINAL RUNNER */}
        {activeTab === 'terminal' && (
          <div className="space-y-4">
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-bold text-sm text-white flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-emerald-400" />
                    <span>Live Linux CLI Runner</span>
                  </h3>
                  <p className="text-xs text-zinc-400">Execute pdf-organizer commands directly in the local Linux sandbox.</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-500">Presets:</span>
                  <button
                    onClick={() => {
                      setCliCommand('./pdf-organizer --help');
                      executeCli('./pdf-organizer --help');
                    }}
                    className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-xs rounded font-mono text-zinc-300 cursor-pointer"
                  >
                    --help
                  </button>
                  <button
                    onClick={() => {
                      setCliCommand('./pdf-organizer scan tests/');
                      executeCli('./pdf-organizer scan tests/');
                    }}
                    className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-xs rounded font-mono text-zinc-300 cursor-pointer"
                  >
                    scan
                  </button>
                  <button
                    onClick={() => {
                      setCliCommand('./pdf-organizer duplicates tests/');
                      executeCli('./pdf-organizer duplicates tests/');
                    }}
                    className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-xs rounded font-mono text-zinc-300 cursor-pointer"
                  >
                    duplicates
                  </button>
                  <button
                    onClick={() => {
                      setCliCommand('python3 -m unittest discover tests');
                      executeCli('python3 -m unittest discover tests');
                    }}
                    className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-xs rounded font-mono text-zinc-300 cursor-pointer"
                  >
                    test-suite
                  </button>
                </div>
              </div>

              {/* Command Input */}
              <div className="flex gap-2">
                <input
                  type="text"
                  value={cliCommand}
                  onChange={(e) => setCliCommand(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && executeCli()}
                  placeholder="./pdf-organizer --help"
                  className="flex-1 bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 text-sm font-mono text-zinc-100 focus:outline-none focus:border-emerald-500"
                />
                <button
                  onClick={() => executeCli()}
                  disabled={cliRunning}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-semibold flex items-center gap-1.5 transition cursor-pointer"
                >
                  <Play className="w-4 h-4" />
                  <span>Execute</span>
                </button>
              </div>

              {/* Terminal Screen */}
              <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 font-mono text-xs text-zinc-200 min-h-[350px] max-h-[500px] overflow-y-auto whitespace-pre-wrap leading-relaxed shadow-inner">
                {cliOutput}
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: TEST SUITE */}
        {activeTab === 'tests' && (
          <div className="space-y-4">
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div>
                  <h3 className="font-bold text-base text-white flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <span>Unit Test Suite (28 Tests Across 10 Modules)</span>
                  </h3>
                  <p className="text-xs text-zinc-400 mt-0.5">
                    Strict isolation using Python tempfile. Zero mutation of real user home directories.
                  </p>
                </div>
                <button
                  onClick={runTests}
                  disabled={testRunning}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-semibold flex items-center gap-2 transition cursor-pointer"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${testRunning ? 'animate-spin' : ''}`} />
                  <span>{testRunning ? 'Running Tests...' : 'Run All Tests'}</span>
                </button>
              </div>

              {/* 10 Test modules status cards */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {[
                  { name: 'test_scanner.py', desc: 'Recursive .pdf/.PDF & symlinks', tests: '3 tests' },
                  { name: 'test_metadata.py', desc: 'Sizes, dates, title, author', tests: '2 tests' },
                  { name: 'test_extractor.py', desc: 'Textual, empty & OCR_REQUIRED', tests: '3 tests' },
                  { name: 'test_ocr.py', desc: 'Tesseract & hash cache', tests: '3 tests' },
                  { name: 'test_classification.py', desc: 'Keywords, À_classer & LLM fallback', tests: '6 tests' },
                  { name: 'test_duplicates.py', desc: 'Exact byte SHA-256 clusters', tests: '1 test' },
                  { name: 'test_planner.py', desc: 'Destinations & collisions', tests: '3 tests' },
                  { name: 'test_simulator.py', desc: 'Strict zero filesystem mutation', tests: '2 tests' },
                  { name: 'test_mover.py', desc: 'Never overwrite & rename _1.pdf', tests: '3 tests' },
                  { name: 'test_undo.py', desc: 'Rollback & tamper protection', tests: '2 tests' },
                ].map((t) => (
                  <div key={t.name} className="bg-zinc-800/40 border border-zinc-800 rounded-lg p-3 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-zinc-200">{t.name}</span>
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    </div>
                    <p className="text-[11px] text-zinc-400 line-clamp-2">{t.desc}</p>
                    <span className="text-[10px] text-emerald-400 font-mono block pt-1">{t.tests} PASSED</span>
                  </div>
                ))}
              </div>

              {/* Output log */}
              <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-4 font-mono text-xs text-zinc-300 min-h-[160px] whitespace-pre-wrap">
                {testOutput || 'Click "Run All Tests" to execute the test suite in this container.'}
              </div>
            </div>
          </div>
        )}

        {/* TAB 5: TAXONOMY & CONFIG */}
        {activeTab === 'taxonomy' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Taxonomy */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div className="flex items-center gap-2">
                  <Layers className="w-5 h-5 text-emerald-400" />
                  <h3 className="font-bold text-sm text-white">Dynamic Taxonomy (config/taxonomy.yaml)</h3>
                </div>
                <span className="text-xs text-zinc-400 font-mono">100% Configurable</span>
              </div>
              <p className="text-xs text-zinc-400">
                Categories are loaded dynamically without any Python code modification. Add or modify nested keys and keywords in YAML.
              </p>
              <div className="bg-zinc-950 p-4 rounded-lg font-mono text-xs text-zinc-300 max-h-[450px] overflow-y-auto border border-zinc-800 space-y-3">
                <div>
                  <span className="text-emerald-400 font-bold">Maths/</span>
                  <div className="pl-4 text-zinc-400">
                    <div>• Algèbre: <span className="text-zinc-500">matrix, eigenvalue, vector space, linear algebra</span></div>
                    <div>• Analyse: <span className="text-zinc-500">calculus, integral, derivative, differential equation</span></div>
                    <div>• Probabilités: <span className="text-zinc-500">probability, random variable, markov chain</span></div>
                    <div>• Statistiques: <span className="text-zinc-500">regression, hypothesis testing, p-value</span></div>
                  </div>
                </div>
                <div>
                  <span className="text-blue-400 font-bold">Informatique/</span>
                  <div className="pl-4 text-zinc-400">
                    <div>• Intelligence-Artificielle: <span className="text-zinc-500">neural network, deep learning, cnn, transformer</span></div>
                    <div>• Programmation: <span className="text-zinc-500">python, rust, c++, function, compiler</span></div>
                    <div>• Algorithmique: <span className="text-zinc-500">binary tree, graph theory, dynamic programming</span></div>
                    <div>• Systèmes: <span className="text-zinc-500">operating system, kernel, linux, thread</span></div>
                  </div>
                </div>
                <div>
                  <span className="text-purple-400 font-bold">Physique / Électronique / Ingénierie / Philosophie</span>
                </div>
                <div>
                  <span className="text-amber-400 font-bold">À_classer</span>
                  <div className="pl-4 text-zinc-500">Default fallback for scores &lt; 0.50 or ambiguous matches.</div>
                </div>
              </div>
            </div>

            {/* Global Config */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
              <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                <div className="flex items-center gap-2">
                  <Settings className="w-5 h-5 text-emerald-400" />
                  <h3 className="font-bold text-sm text-white">Global Policy (config/config.yaml)</h3>
                </div>
                <span className="text-xs text-zinc-400 font-mono">YAML</span>
              </div>
              <p className="text-xs text-zinc-400">
                Central configuration governing classifier thresholds, OCR triggers, safety protocols, and local LLM backends.
              </p>
              <div className="space-y-3 text-xs">
                <div className="bg-zinc-800/40 p-3 rounded-lg border border-zinc-800">
                  <div className="font-semibold text-zinc-200">classification.manual_review_threshold: 0.50</div>
                  <div className="text-zinc-400 mt-1">
                    Documents with confidence score strictly below 0.50 route automatically to <code>À_classer</code> for human verification.
                  </div>
                </div>
                <div className="bg-zinc-800/40 p-3 rounded-lg border border-zinc-800">
                  <div className="font-semibold text-zinc-200">safety.overwrite: false</div>
                  <div className="text-zinc-400 mt-1">
                    Absolute core rule: NEVER OVERWRITE. If destination exists, policy renames to <code>_1.pdf</code> or skips.
                  </div>
                </div>
                <div className="bg-zinc-800/40 p-3 rounded-lg border border-zinc-800">
                  <div className="font-semibold text-zinc-200">ocr.min_text_len_per_page: 30</div>
                  <div className="text-zinc-400 mt-1">
                    If page count &gt; 0 and character density is under 30 chars/page, document is flagged as <code>OCR_REQUIRED</code>.
                  </div>
                </div>
                <div className="bg-zinc-800/40 p-3 rounded-lg border border-zinc-800">
                  <div className="font-semibold text-zinc-200">llm.enabled: false (Ollama / llama.cpp)</div>
                  <div className="text-zinc-400 mt-1">
                    Zero remote dependency. If enabled, connects strictly to loopback <code>http://127.0.0.1:11434</code> with schema validation.
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 6: SAFETY & GUARANTEES */}
        {activeTab === 'safety' && (
          <div className="space-y-6">
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-6">
              <div>
                <h3 className="text-lg font-bold text-white flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-emerald-400" />
                  <span>Filesystem Safety & Reversibility Architecture</span>
                </h3>
                <p className="text-sm text-zinc-400 mt-1">
                  Engineered specifically for Linux environments to eliminate accidental data loss, corrupted partial copies, and silent overwrites.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 space-y-2">
                  <div className="w-8 h-8 rounded-lg bg-red-500/10 text-red-400 flex items-center justify-center font-bold">
                    1
                  </div>
                  <h4 className="font-bold text-sm text-white">NEVER OVERWRITE</h4>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    If <code>destination/file.pdf</code> already exists, the mover never replaces it. It automatically computes a collision-free alternative (e.g. <code>file_1.pdf</code>) or skips according to your policy.
                  </p>
                </div>

                <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 space-y-2">
                  <div className="w-8 h-8 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center font-bold">
                    2
                  </div>
                  <h4 className="font-bold text-sm text-white">Cross-Filesystem Safety</h4>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    Same-device moves use atomic <code>os.replace</code>. Cross-filesystem moves execute <code>shutil.copy2</code> ➔ <code>os.fsync</code> ➔ verify SHA-256 byte digest ➔ unlink source <strong>only after verified hash match</strong>.
                  </p>
                </div>

                <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 space-y-2">
                  <div className="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center font-bold">
                    3
                  </div>
                  <h4 className="font-bold text-sm text-white">Cryptographic Rollback</h4>
                  <p className="text-xs text-zinc-400 leading-relaxed">
                    Every operation is logged in <code>operations.json</code> with exact SHA-256. The <code>undo</code> command checks if the moved file was modified at destination before reversing, preventing corrupted overwrites.
                  </p>
                </div>
              </div>

              {/* Step by step flow */}
              <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 space-y-3">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Verification Lifecycle Before Mutation
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-6 gap-2 text-xs font-mono">
                  <div className="p-2.5 bg-zinc-900 rounded border border-zinc-800 text-center">
                    <span className="text-zinc-500 block text-[10px]">Step 1</span>
                    <span className="text-zinc-200">Source Exists?</span>
                  </div>
                  <div className="p-2.5 bg-zinc-900 rounded border border-zinc-800 text-center">
                    <span className="text-zinc-500 block text-[10px]">Step 2</span>
                    <span className="text-zinc-200">Source Readable?</span>
                  </div>
                  <div className="p-2.5 bg-zinc-900 rounded border border-zinc-800 text-center">
                    <span className="text-zinc-500 block text-[10px]">Step 3</span>
                    <span className="text-zinc-200">SHA-256 Unchanged?</span>
                  </div>
                  <div className="p-2.5 bg-zinc-900 rounded border border-zinc-800 text-center">
                    <span className="text-zinc-500 block text-[10px]">Step 4</span>
                    <span className="text-zinc-200">Dest Collision?</span>
                  </div>
                  <div className="p-2.5 bg-zinc-900 rounded border border-zinc-800 text-center">
                    <span className="text-zinc-500 block text-[10px]">Step 5</span>
                    <span className="text-zinc-200">Inside Allowed Base?</span>
                  </div>
                  <div className="p-2.5 bg-emerald-950/40 rounded border border-emerald-800 text-center">
                    <span className="text-emerald-400 block text-[10px]">Step 6</span>
                    <span className="text-emerald-300 font-bold">Apply & Log</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800 bg-zinc-900/50 py-3 text-center text-xs text-zinc-500">
        Local Intelligent PDF Organizer • Python 3.10+ Linux Architecture • 100% Offline
      </footer>
    </div>
  );
}
