'use strict';
/**
 * PRUVALEX PruvaGraph — Multi-Language Code Analyzer
 * 
 * 100% FREE — no LLM, no API key, no cost.
 * Uses regex-based AST-lite parsing for 20+ languages.
 * 
 * Detects:
 *   - Imports / dependencies
 *   - Class / interface / type definitions
 *   - Function / method signatures
 *   - Module exports
 * 
 * Returns: { nodes: [], edges: [], source_file: string }
 */

const path = require('path');

// ─────────────────────────────────────────────────────────────────────────────
// Language detection by extension
// ─────────────────────────────────────────────────────────────────────────────

const LANG_MAP = {
  '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript', '.cjs': 'javascript',
  '.ts': 'typescript', '.tsx': 'typescript', '.mts': 'typescript',
  '.py': 'python', '.pyw': 'python',
  '.go': 'go',
  '.rs': 'rust',
  '.java': 'java',
  '.kt': 'kotlin', '.kts': 'kotlin',
  '.swift': 'swift',
  '.cs': 'csharp',
  '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp', '.hpp': 'cpp', '.h': 'cpp',
  '.c': 'c',
  '.rb': 'ruby',
  '.php': 'php',
  '.vue': 'vue',
  '.svelte': 'svelte',
  '.dart': 'dart',
  '.scala': 'scala',
  '.zig': 'zig',
  '.lua': 'lua',
  '.r': 'r', '.R': 'r',
  '.sh': 'bash', '.bash': 'bash',
  '.yaml': 'yaml', '.yml': 'yaml',
  '.json': 'json',
  '.toml': 'toml',
  '.md': 'markdown',
  '.css': 'css', '.scss': 'css', '.sass': 'css', '.less': 'css',
  '.html': 'html', '.htm': 'html',
  '.tf': 'terraform', '.hcl': 'terraform',
  '.sql': 'sql',
};

// ─────────────────────────────────────────────────────────────────────────────
// Per-language patterns
// ─────────────────────────────────────────────────────────────────────────────

const PATTERNS = {
  javascript: {
    imports: [
      /import\s+(?:[\w*{}\s,]+\s+from\s+)?['"]([^'"]+)['"]/g,
      /require\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
      /import\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
    ],
    classes:   [/class\s+(\w+)(?:\s+extends\s+(\w+))?/g],
    functions: [/(?:function|const|let|var)\s+(\w+)\s*(?:=\s*(?:async\s+)?(?:\([^)]*\)|[\w]+)\s*=>|\()/g,
                /(?:async\s+)?function\s+(\w+)\s*\(/g],
    exports:   [/export\s+(?:default\s+)?(?:class|function|const|let|var)?\s*(\w+)/g],
    interfaces:[/interface\s+(\w+)/g, /type\s+(\w+)\s*=/g],
  },
  typescript: {
    imports: [
      /import\s+(?:type\s+)?(?:[\w*{}\s,]+\s+from\s+)?['"]([^'"]+)['"]/g,
      /require\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
    ],
    classes:    [/class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+[\w,\s]+)?/g],
    functions:  [/(?:function|const|let|var)\s+(\w+)\s*(?:<[^>]*>)?\s*(?:=\s*(?:async\s+)?\(?|:\s*\w+\s*=)/g,
                 /(?:async\s+)?function\s+(\w+)\s*(?:<[^>]*>)?\s*\(/g],
    exports:    [/export\s+(?:default\s+)?(?:class|function|const|let|var|type|interface|enum)?\s*(\w+)/g],
    interfaces: [/interface\s+(\w+)/g, /type\s+(\w+)\s*(?:<[^>]*>)?\s*=/g, /enum\s+(\w+)/g],
  },
  python: {
    imports: [
      /^import\s+([\w.]+)(?:\s+as\s+\w+)?/gm,
      /^from\s+([\w.]+)\s+import/gm,
    ],
    classes:   [/^class\s+(\w+)(?:\s*\(([^)]*)\))?/gm],
    functions: [/^(?:async\s+)?def\s+(\w+)\s*\(/gm],
    exports:   [/__all__\s*=\s*\[([^\]]+)\]/g],
    decorators:[/@(\w+)(?:\.\w+)*/g],
  },
  go: {
    imports: [
      /import\s+"([\w./]+)"/g,
      /import\s+\w+\s+"([\w./]+)"/g,
      /"([\w./]+)"/g,
    ],
    classes:   [/type\s+(\w+)\s+struct/g, /type\s+(\w+)\s+interface/g],
    functions: [/func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\(/g],
    exports:   [],  // Go exports by capitalization
    interfaces:[/type\s+(\w+)\s+interface/g],
  },
  rust: {
    imports: [
      /use\s+([\w:]+)(?:::\{[^}]+\}|::\*)?/g,
      /extern\s+crate\s+(\w+)/g,
    ],
    classes:   [/(?:pub\s+)?struct\s+(\w+)/g, /(?:pub\s+)?enum\s+(\w+)/g],
    functions: [/(?:pub\s+)?(?:async\s+)?fn\s+(\w+)/g],
    exports:   [/pub\s+(?:struct|enum|fn|type|trait|mod)\s+(\w+)/g],
    interfaces:[/(?:pub\s+)?trait\s+(\w+)/g],
  },
  java: {
    imports: [/^import\s+([\w.]+)\s*;/gm],
    classes: [/(?:public|private|protected)?\s*(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?/g,
              /(?:public|private|protected)?\s*interface\s+(\w+)/g],
    functions: [/(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)\s*(?:throws[^{]*)?\{/g],
    exports:   [],
    interfaces:[/interface\s+(\w+)/g],
  },
  kotlin: {
    imports: [/^import\s+([\w.]+)(?:\.\*)?/gm],
    classes: [/(?:data\s+|sealed\s+|abstract\s+|open\s+)?class\s+(\w+)/g,
              /object\s+(\w+)/g, /interface\s+(\w+)/g],
    functions: [/(?:fun|suspend\s+fun|private\s+fun|public\s+fun)\s+(\w+)/g],
    exports:   [],
    interfaces:[/interface\s+(\w+)/g],
  },
  csharp: {
    imports: [/^using\s+([\w.]+)\s*;/gm],
    classes: [/(?:public|private|internal|protected)?\s*(?:abstract\s+|static\s+|sealed\s+)?class\s+(\w+)/g,
              /(?:public|private|internal)?\s*interface\s+(\w+)/g],
    functions: [/(?:public|private|protected|internal|static|async|\s)+\w+\s+(\w+)\s*\([^)]*\)\s*\{/g],
    exports:   [],
    interfaces:[/interface\s+(\w+)/g],
  },
  swift: {
    imports: [/^import\s+(\w+)/gm],
    classes: [/(?:public\s+|open\s+|private\s+|internal\s+)?(?:class|struct|enum|actor)\s+(\w+)/g,
              /(?:public\s+)?protocol\s+(\w+)/g],
    functions: [/(?:public\s+|private\s+|internal\s+|open\s+)?(?:override\s+)?func\s+(\w+)/g],
    exports:   [/public\s+(?:class|struct|enum|func|var|let|protocol)\s+(\w+)/g],
    interfaces:[/protocol\s+(\w+)/g],
  },
  dart: {
    imports: [/^import\s+'([^']+)'/gm, /^import\s+"([^"]+)"/gm],
    classes: [/(?:abstract\s+)?class\s+(\w+)/g, /mixin\s+(\w+)/g],
    functions: [/(?:Future<\w+>|void|String|int|bool|List|Map|\w+)\s+(\w+)\s*\([^)]*\)\s*(?:async\s*)?\{/g],
    exports:   [],
    interfaces:[],
  },
  ruby: {
    imports: [/require\s+['"]([^'"]+)['"]/g, /require_relative\s+['"]([^'"]+)['"]/g, /include\s+(\w+)/g],
    classes: [/class\s+(\w+)(?:\s*<\s*(\w+))?/g, /module\s+(\w+)/g],
    functions: [/def\s+(?:self\.)?(\w+)/g],
    exports:   [],
    interfaces:[/module\s+(\w+)/g],
  },
  vue: {
    imports: [
      /import\s+(?:[\w*{}\s,]+\s+from\s+)?['"]([^'"]+)['"]/g,
      /require\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
    ],
    classes:   [/name:\s*['"](\w+)['"]/g],
    functions: [/methods:\s*\{([^}]+)\}/g],
    exports:   [/export\s+default\s+/g],
    interfaces:[/components:\s*\{([^}]+)\}/g],
  },
  css: {
    imports: [/@import\s+(?:url\s*\(\s*)?['"]?([^'"\s)]+)['"]?/g],
    classes:   [/\.([\w-]+)\s*\{/g],
    functions: [],
    exports:   [],
    interfaces:[/--[\w-]+\s*:/g],  // CSS variables
  },
  generic: {
    imports: [/(?:import|include|require|use)\s+['"]?([^\s'"<>]+)['"]?/g],
    classes:   [/(?:class|interface|struct|type)\s+(\w+)/g],
    functions: [/(?:function|def|fn|func|method|fun)\s+(\w+)/g],
    exports:   [],
    interfaces:[],
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// Main export
// ─────────────────────────────────────────────────────────────────────────────

class Analyzer {
  /**
   * Analyze a single file. Returns extraction result.
   * @param {string} filePath  Absolute or relative path
   * @param {string} content   File content (string)
   * @returns {{ nodes: object[], edges: object[], source_file: string, lang: string }}
   */
  static analyze(filePath, content) {
    const ext = path.extname(filePath).toLowerCase();
    const lang = LANG_MAP[ext] || 'generic';
    const patterns = PATTERNS[lang] || PATTERNS.generic;
    const stem = path.basename(filePath, ext);
    const relPath = filePath.replace(/\\/g, '/');

    const nodes = [];
    const edges = [];
    const nodeIds = new Set();

    // Helper: add node if not already added
    const addNode = (id, label, type, extra = {}) => {
      if (!nodeIds.has(id)) {
        nodeIds.add(id);
        nodes.push({ id, label, type, file: relPath, lang, ...extra });
      }
    };

    // Helper: add edge
    const addEdge = (source, target, relation = 'imports') => {
      edges.push({ source, target, relation });
    };

    // Module node (the file itself)
    const moduleId = relPath;
    addNode(moduleId, stem, 'module', {
      summary: `${lang} module: ${stem}`,
      community: null,
    });

    // ── Classes / Structs / Interfaces ───────────────────────────────────────
    for (const pattern of (patterns.classes || [])) {
      const regex = new RegExp(pattern.source, pattern.flags);
      let match;
      while ((match = regex.exec(content)) !== null) {
        const className = match[1];
        if (!className || className.length > 80) continue;
        const nodeId = `${relPath}::${className}`;
        addNode(nodeId, className, 'class', {
          summary: `${lang} class in ${stem}`,
        });
        addEdge(moduleId, nodeId, 'defines');

        // Inheritance edge
        if (match[2]) {
          addEdge(nodeId, match[2], 'extends');
        }
      }
    }

    // ── Interfaces / Types ───────────────────────────────────────────────────
    for (const pattern of (patterns.interfaces || [])) {
      const regex = new RegExp(pattern.source, pattern.flags);
      let match;
      while ((match = regex.exec(content)) !== null) {
        const name = match[1];
        if (!name || name.length > 80) continue;
        const nodeId = `${relPath}::${name}`;
        addNode(nodeId, name, 'interface', {
          summary: `${lang} interface/type in ${stem}`,
        });
        addEdge(moduleId, nodeId, 'defines');
      }
    }

    // ── Functions / Methods ──────────────────────────────────────────────────
    let funcCount = 0;
    for (const pattern of (patterns.functions || [])) {
      const regex = new RegExp(pattern.source, pattern.flags);
      let match;
      while ((match = regex.exec(content)) !== null) {
        const fnName = match[1];
        if (!fnName || fnName.length > 80) continue;
        // Skip common noise words
        if (['if', 'for', 'while', 'return', 'new', 'delete', 'const', 'let', 'var'].includes(fnName)) continue;
        const nodeId = `${relPath}::${fnName}`;
        addNode(nodeId, fnName, 'function', {
          summary: `${lang} function in ${stem}`,
        });
        addEdge(moduleId, nodeId, 'defines');
        funcCount++;
        if (funcCount > 50) break;  // cap to avoid noise in massive files
      }
    }

    // ── Import edges ─────────────────────────────────────────────────────────
    const importedModules = new Set();
    for (const pattern of (patterns.imports || [])) {
      const regex = new RegExp(pattern.source, pattern.flags);
      let match;
      while ((match = regex.exec(content)) !== null) {
        const importPath = match[1];
        if (!importPath || importPath.length > 200) continue;
        if (importedModules.has(importPath)) continue;
        importedModules.add(importPath);

        // Resolve relative imports
        const targetId = _resolveImport(importPath, filePath);
        addEdge(moduleId, targetId, 'imports');

        // Add a stub node for the target if it's an external package
        if (!importPath.startsWith('.') && !importPath.startsWith('/')) {
          const pkgName = importPath.split('/')[0].replace('@', '').split('/').slice(0, 2).join('/');
          if (!nodeIds.has(targetId)) {
            addNode(targetId, pkgName, 'external', {
              summary: `External package: ${pkgName}`,
            });
          }
        }
      }
    }

    return { nodes, edges, source_file: relPath, lang };
  }

  /**
   * Get language for a file path
   */
  static getLang(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    return LANG_MAP[ext] || null;
  }

  /**
   * Check if a file should be analyzed (is a code file)
   */
  static isCode(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    return ext in LANG_MAP;
  }

  /**
   * Get stats about what was analyzed
   */
  static getStats(result) {
    const types = {};
    for (const node of result.nodes) {
      types[node.type] = (types[node.type] || 0) + 1;
    }
    return { nodes: result.nodes.length, edges: result.edges.length, types };
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function _resolveImport(importPath, fromFile) {
  if (!importPath.startsWith('.')) {
    // External package — use package name as ID
    const parts = importPath.split('/');
    const name = importPath.startsWith('@') ? parts.slice(0, 2).join('/') : parts[0];
    return `pkg:${name}`;
  }
  // Relative import — resolve to normalized path
  const dir = path.dirname(fromFile);
  const resolved = path.normalize(path.join(dir, importPath)).replace(/\\/g, '/');
  return resolved;
}

module.exports = { Analyzer, LANG_MAP };
