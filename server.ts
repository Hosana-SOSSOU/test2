import express from 'express';
import { createServer as createViteServer } from 'vite';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';
import { exec } from 'child_process';
import util from 'util';

const execPromise = util.promisify(exec);
const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function startServer() {
  const app = express();
  const port = process.env.PORT || 3000;

  app.use(express.json());

  // API 1: Run test suite
  app.get('/api/tests/run', async (_req, res) => {
    try {
      const { stdout, stderr } = await execPromise('python3 -m unittest discover tests', {
        cwd: __dirname,
      });
      res.json({
        success: true,
        output: (stdout + '\n' + stderr).trim(),
      });
    } catch (err: any) {
      res.json({
        success: false,
        output: (err.stdout || '') + '\n' + (err.stderr || err.message || ''),
      });
    }
  });

  // API 2: Get project file tree
  app.get('/api/project-tree', (_req, res) => {
    try {
      const getTree = (dir: string, baseDir: string = ''): any[] => {
        const items = fs.readdirSync(dir, { withFileTypes: true });
        const list: any[] = [];
        for (const it of items) {
          if (it.name.startsWith('.') || it.name === 'node_modules' || it.name === 'dist' || it.name === '__pycache__') {
            continue;
          }
          const relPath = path.join(baseDir, it.name);
          const fullPath = path.join(dir, it.name);
          if (it.isDirectory()) {
            list.push({
              name: it.name,
              path: relPath,
              type: 'directory',
              children: getTree(fullPath, relPath),
            });
          } else {
            list.push({
              name: it.name,
              path: relPath,
              type: 'file',
              size: fs.statSync(fullPath).size,
            });
          }
        }
        return list;
      };

      const tree = [
        {
          name: 'src/pdf_organizer',
          path: 'src/pdf_organizer',
          type: 'directory',
          children: getTree(path.join(__dirname, 'src/pdf_organizer'), 'src/pdf_organizer'),
        },
        {
          name: 'config',
          path: 'config',
          type: 'directory',
          children: getTree(path.join(__dirname, 'config'), 'config'),
        },
        {
          name: 'tests',
          path: 'tests',
          type: 'directory',
          children: getTree(path.join(__dirname, 'tests'), 'tests'),
        },
        {
          name: 'pyproject.toml',
          path: 'pyproject.toml',
          type: 'file',
          size: fs.statSync(path.join(__dirname, 'pyproject.toml')).size,
        },
        {
          name: 'README.md',
          path: 'README.md',
          type: 'file',
          size: fs.statSync(path.join(__dirname, 'README.md')).size,
        },
      ];

      res.json({ tree });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // API 3: Get file content
  app.get('/api/file-content', (req, res) => {
    try {
      const filePath = req.query.path as string;
      if (!filePath) {
        return res.status(400).json({ error: 'Missing path parameter' });
      }

      // Security: ensure path stays within workspace root
      const resolved = path.resolve(__dirname, filePath);
      if (!resolved.startsWith(__dirname)) {
        return res.status(403).json({ error: 'Forbidden' });
      }

      if (!fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) {
        return res.status(404).json({ error: 'File not found' });
      }

      const content = fs.readFileSync(resolved, 'utf-8');
      res.json({ path: filePath, content });
    } catch (err: any) {
      res.status(500).json({ error: err.message });
    }
  });

  // API 4: Execute CLI command safely
  app.post('/api/cli/run', async (req, res) => {
    try {
      const { command } = req.body;
      if (!command || typeof command !== 'string') {
        return res.status(400).json({ error: 'Missing command' });
      }

      // Allow only pdf-organizer or python3 -m src.pdf_organizer.cli
      const trimmed = command.trim();
      if (!trimmed.startsWith('./pdf-organizer') && !trimmed.startsWith('pdf-organizer') && !trimmed.startsWith('python3')) {
        return res.status(400).json({ error: 'Only pdf-organizer commands are permitted' });
      }

      // Prevent shell chaining attacks
      if (/[;&|`]/.test(trimmed)) {
        return res.status(400).json({ error: 'Command chaining characters are disallowed' });
      }

      const { stdout, stderr } = await execPromise(trimmed, {
        cwd: __dirname,
        timeout: 15000,
      });

      res.json({
        success: true,
        output: (stdout + '\n' + stderr).trim(),
      });
    } catch (err: any) {
      res.json({
        success: false,
        output: (err.stdout || '') + '\n' + (err.stderr || err.message || ''),
      });
    }
  });

  // API 5: Run demo workbench
  app.post('/api/demo/setup-and-process', async (_req, res) => {
    try {
      const demoScript = `
import tempfile, json, os
from pathlib import Path
from src.pdf_organizer.models import Document, TextStatus
from src.pdf_organizer.taxonomy import Taxonomy
from src.pdf_organizer.classification.rule_based import RuleBasedClassifier
from src.pdf_organizer.planner import MovePlanner
from src.pdf_organizer.simulator import Simulator
from src.pdf_organizer.duplicates import DuplicateDetector
from src.pdf_organizer.hashing import compute_file_sha256

demo_dir = Path("/tmp/pdf_organizer_demo")
demo_dir.mkdir(parents=True, exist_ok=True)
source_dir = demo_dir / "Incoming_Downloads"
source_dir.mkdir(parents=True, exist_ok=True)
target_dir = demo_dir / "Organized_Library"
target_dir.mkdir(parents=True, exist_ok=True)

# Generate sample documents
files_data = [
    ("linear_algebra_basis.pdf", "%PDF-1.4\\nLinear Algebra Lecture: Eigenvalues, vector space transformations and matrix diagonalization.", "Maths/Algèbre"),
    ("deep_residual_networks.pdf", "%PDF-1.4\\nDeep learning with convolutional neural network (CNN), backpropagation and gradient descent.", "Informatique/Intelligence-Artificielle"),
    ("advanced_calculus.pdf", "%PDF-1.4\\nDifferential equation analysis, calculus integrals, and series convergence.", "Maths/Analyse"),
    ("thermodynamics_intro.pdf", "%PDF-1.4\\nThermodynamics cycles, entropy, and heat engines in physics.", "Physique"),
    ("scanned_receipt_ocr.pdf", "%PDF-1.4\\n[IMAGE ONLY - SCANNED DOCUMENT REQUIRING OCR]", "OCR_REQUIRED"),
    ("duplicate_deep_net_copy.pdf", "%PDF-1.4\\nDeep learning with convolutional neural network (CNN), backpropagation and gradient descent.", "Informatique/Intelligence-Artificielle"),
    ("family_cooking_recipe.pdf", "%PDF-1.4\\nRecipe for homemade sourdough bread and chocolate chip cookies.", "À_classer"),
]

docs = []
for name, text, expected in files_data:
    p = source_dir / name
    p.write_text(text, encoding="utf-8")
    sha = compute_file_sha256(p)
    status = TextStatus.OCR_REQUIRED if "IMAGE ONLY" in text else TextStatus.TEXT_AVAILABLE
    docs.append(Document(
        path=p,
        filename=name,
        size_bytes=p.stat().st_size,
        modified_at=None,
        title=name.replace(".pdf", "").replace("_", " ").title(),
        text=text,
        text_length=len(text),
        text_status=status,
        sha256=sha,
    ))

tax = Taxonomy.load("config/taxonomy.yaml")
clf = RuleBasedClassifier(tax, manual_review_threshold=0.50)

classifications = {}
for d in docs:
    classifications[str(d.path)] = clf.classify(d)

planner = MovePlanner(target_base_dir=target_dir)
pairs = [(d, classifications[str(d.path)]) for d in docs]
plans = planner.plan_all(pairs)

duplicates = DuplicateDetector().find_duplicates_from_documents(docs)
sim = Simulator(allowed_base_dir=demo_dir)
sim_result = sim.simulate(plans)

out = {
    "documents": [d.to_dict() for d in docs],
    "classifications": {k: v.to_dict() for k, v in classifications.items()},
    "plans": [p.to_dict() for p in plans],
    "duplicates": [g.to_dict() for g in duplicates],
    "simulation": {
        "total": sim_result.total_plans,
        "would_move": sim_result.would_move,
        "collisions": sim_result.collisions,
        "manual_reviews": sim_result.manual_reviews,
        "report_text": sim_result.format_report()
    }
}
print(json.dumps(out))
`;
      const { stdout } = await execPromise(`python3 -c '${demoScript.replace(/'/g, "'\\''")}'`, {
        cwd: __dirname,
      });

      const parsed = JSON.parse(stdout);
      res.json(parsed);
    } catch (err: any) {
      res.status(500).json({ error: err.message, stack: err.stack });
    }
  });

  // Mount Vite dev server
  const vite = await createViteServer({
    server: { middlewareMode: true },
    appType: 'spa',
  });

  app.use(vite.middlewares);

  app.listen(port, () => {
    console.log(`Local Intelligent PDF Organizer web server running at http://localhost:${port}`);
  });
}

startServer();
