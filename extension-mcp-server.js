#!/usr/bin/env node
/**
 * PRUVALEX PruvaGraph — MCP Server for Claude Code
 * 
 * Allows Claude to query savings receipt data and run PruvaGraph operations.
 * 
 * Usage:
 *   node extension-mcp-server.js
 * 
 * In Claude Code:
 *   use_mcp_tool("pruvagraph", "get_savings_receipt")
 *   use_mcp_tool("pruvagraph", "get_cost_report")
 *   use_mcp_tool("pruvagraph", "run_build")
 */

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

// ─────────────────────────────────────────────────────────────────────────────
// MCP Server Implementation
// ─────────────────────────────────────────────────────────────────────────────

class PruvaGraphMCPServer {
  constructor() {
    this.workspaceRoot = process.cwd();
    this.outDir = path.join(this.workspaceRoot, 'pruvagraph-out');
  }

  /**
   * Get latest savings receipt data
   */
  getSavingsReceipt() {
    const costReportPath = path.join(this.outDir, 'cost_report.json');
    const graphJsonPath = path.join(this.outDir, 'graph.json');

    let costData = null;
    let graphData = null;

    try {
      if (fs.existsSync(costReportPath)) {
        costData = JSON.parse(fs.readFileSync(costReportPath, 'utf8'));
      }
      if (fs.existsSync(graphJsonPath)) {
        graphData = JSON.parse(fs.readFileSync(graphJsonPath, 'utf8'));
      }
    } catch (err) {
      return { error: `Failed to read cost data: ${err.message}` };
    }

    if (!costData) {
      return { error: 'No cost report found. Run "pruvagraph build" first.' };
    }

    // Format receipt
    const costSaved = costData.cost_saved_usd || 0;
    const savingsPct = costData.savings_pct || 0;
    const actualCost = costData.actual_cost_usd || 0;
    const naiveCost = costData.naive_cost_usd || 0;
    const tokensSaved = Math.round((naiveCost - actualCost) * 1_000_000 / 3);
    const callsSaved = costData.calls_saved || 0;
    const cacheHits = costData.cache_hits || 0;
    const nodeCount = graphData?.nodes?.length || 0;
    const edgeCount = (graphData?.links || graphData?.edges || []).length || 0;
    const runTime = costData.run_duration_seconds || 0;

    return {
      success: true,
      receipt: {
        costSaved: {
          dollars: costSaved.toFixed(2),
          percentage: savingsPct.toFixed(1),
        },
        metrics: {
          tokensSaved: tokensSaved.toLocaleString(),
          apiCallsSaved: callsSaved.toLocaleString(),
          cacheHits: cacheHits.toLocaleString(),
          nodesInGraph: nodeCount.toLocaleString(),
          edgesInGraph: edgeCount.toLocaleString(),
        },
        costs: {
          actualCost: actualCost.toFixed(6),
          naiveCostEstimate: naiveCost.toFixed(4),
          costSaved: costSaved.toFixed(4),
          runDuration: runTime.toFixed(2),
        },
        timestamp: new Date().toISOString(),
      },
    };
  }

  /**
   * Get full cost report
   */
  getCostReport() {
    const costReportPath = path.join(this.outDir, 'cost_report.json');

    try {
      if (!fs.existsSync(costReportPath)) {
        return { error: 'No cost report found. Run "pruvagraph build" first.' };
      }

      const data = JSON.parse(fs.readFileSync(costReportPath, 'utf8'));
      return {
        success: true,
        report: data,
      };
    } catch (err) {
      return { error: `Failed to read cost report: ${err.message}` };
    }
  }

  /**
   * Get graph metadata
   */
  getGraphMetadata() {
    const graphJsonPath = path.join(this.outDir, 'graph.json');
    const graphReportPath = path.join(this.outDir, 'GRAPH_REPORT.md');

    try {
      let graphData = null;
      let report = null;

      if (fs.existsSync(graphJsonPath)) {
        graphData = JSON.parse(fs.readFileSync(graphJsonPath, 'utf8'));
      }

      if (fs.existsSync(graphReportPath)) {
        report = fs.readFileSync(graphReportPath, 'utf8');
      }

      return {
        success: true,
        metadata: {
          nodeCount: graphData?.nodes?.length || 0,
          edgeCount: (graphData?.links || graphData?.edges || []).length || 0,
          communities: graphData?.communities?.length || 0,
          graphPath: graphJsonPath,
          reportPath: graphReportPath,
          hasReport: !!report,
          reportPreview: report ? report.substring(0, 500) : null,
        },
      };
    } catch (err) {
      return { error: `Failed to read graph metadata: ${err.message}` };
    }
  }

  /**
   * Run build command
   */
  async runBuild(options = {}) {
    const args = ['.'];

    if (options.backend) args.push('--backend', options.backend);
    if (options.dedupThreshold) args.push('--dedup-threshold', String(options.dedupThreshold));
    if (options.stream) args.push('--stream');

    return new Promise((resolve) => {
      const proc = spawn('pruvagraph', args, {
        cwd: this.workspaceRoot,
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => {
        stdout += data.toString();
      });

      proc.stderr?.on('data', (data) => {
        stderr += data.toString();
      });

      proc.on('close', (code) => {
        if (code === 0) {
          // Build succeeded, fetch receipt
          const receipt = this.getSavingsReceipt();
          resolve({
            success: true,
            exitCode: code,
            message: 'Build completed successfully',
            receipt: receipt.receipt || null,
            logs: stdout,
          });
        } else {
          resolve({
            success: false,
            exitCode: code,
            error: 'Build failed',
            logs: stdout,
            stderr,
          });
        }
      });

      proc.on('error', (err) => {
        resolve({
          success: false,
          error: `Failed to run pruvagraph: ${err.message}`,
        });
      });
    });
  }

  /**
   * Run dry run estimate
   */
  async runDryRun(options = {}) {
    const args = ['.', '--dry-run'];

    if (options.backend) args.push('--backend', options.backend);

    return new Promise((resolve) => {
      const proc = spawn('pruvagraph', args, {
        cwd: this.workspaceRoot,
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => {
        stdout += data.toString();
      });

      proc.stderr?.on('data', (data) => {
        stderr += data.toString();
      });

      proc.on('close', (code) => {
        if (code === 0) {
          resolve({
            success: true,
            exitCode: code,
            message: 'Dry run completed',
            estimate: this._parseEstimate(stdout),
            logs: stdout,
          });
        } else {
          resolve({
            success: false,
            exitCode: code,
            error: 'Dry run failed',
            logs: stdout,
            stderr,
          });
        }
      });

      proc.on('error', (err) => {
        resolve({
          success: false,
          error: `Failed to run dry run: ${err.message}`,
        });
      });
    });
  }

  /**
   * Parse estimate from CLI output
   */
  _parseEstimate(output) {
    const lines = output.split('\n');
    const estimate = {};

    lines.forEach((line) => {
      if (line.includes('Estimated tokens')) {
        const match = line.match(/(\d+)/);
        if (match) estimate.tokens = parseInt(match[1]);
      }
      if (line.includes('Estimated cost')) {
        const match = line.match(/\$([0-9.]+)/);
        if (match) estimate.costUsd = parseFloat(match[1]);
      }
      if (line.includes('savings')) {
        const match = line.match(/(\d+\.?\d*)%/);
        if (match) estimate.savingsPct = parseFloat(match[1]);
      }
    });

    return estimate;
  }

  /**
   * Query the graph
   */
  async runQuery(question, options = {}) {
    const args = ['query', question];

    if (options.backend) args.push('--backend', options.backend);

    return new Promise((resolve) => {
      const proc = spawn('pruvagraph', args, {
        cwd: this.workspaceRoot,
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      let stdout = '';
      let stderr = '';

      proc.stdout?.on('data', (data) => {
        stdout += data.toString();
      });

      proc.stderr?.on('data', (data) => {
        stderr += data.toString();
      });

      proc.on('close', (code) => {
        if (code === 0) {
          resolve({
            success: true,
            exitCode: code,
            answer: stdout,
          });
        } else {
          resolve({
            success: false,
            exitCode: code,
            error: 'Query failed',
            stderr,
          });
        }
      });

      proc.on('error', (err) => {
        resolve({
          success: false,
          error: `Failed to run query: ${err.message}`,
        });
      });
    });
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// stdio Transport (for Claude MCP)
// ─────────────────────────────────────────────────────────────────────────────

class StdioMCPTransport {
  constructor() {
    this.server = new PruvaGraphMCPServer();
    this.requestHandlers = {
      'get_savings_receipt': () => this.server.getSavingsReceipt(),
      'get_cost_report': () => this.server.getCostReport(),
      'get_graph_metadata': () => this.server.getGraphMetadata(),
      'run_build': (params) => this.server.runBuild(params),
      'run_dry_run': (params) => this.server.runDryRun(params),
      'run_query': (params) => this.server.runQuery(params.question, params.options),
    };

    this.startServer();
  }

  startServer() {
    process.stdin.on('data', (data) => {
      try {
        const request = JSON.parse(data.toString());
        this.handleRequest(request);
      } catch (err) {
        this.sendError(`JSON parse error: ${err.message}`);
      }
    });

    process.stdin.on('end', () => {
      process.exit(0);
    });

    // Log startup message to stderr (MCP convention)
    console.error('[MCP] PRUVALEX PruvaGraph Server started');
    console.error('[MCP] Available tools:');
    console.error('  • get_savings_receipt');
    console.error('  • get_cost_report');
    console.error('  • get_graph_metadata');
    console.error('  • run_build');
    console.error('  • run_dry_run');
    console.error('  • run_query');
  }

  async handleRequest(request) {
    const { id, method, params } = request;

    if (!this.requestHandlers[method]) {
      this.sendError(`Unknown method: ${method}`, id);
      return;
    }

    try {
      const result = await this.requestHandlers[method](params);
      this.sendResponse(id, result);
    } catch (err) {
      this.sendError(`Error: ${err.message}`, id);
    }
  }

  sendResponse(id, result) {
    const response = {
      jsonrpc: '2.0',
      id,
      result,
    };
    console.log(JSON.stringify(response));
  }

  sendError(message, id) {
    const response = {
      jsonrpc: '2.0',
      id,
      error: {
        code: -1,
        message,
      },
    };
    console.log(JSON.stringify(response));
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────────────────

if (require.main === module) {
  new StdioMCPTransport();
}

module.exports = { PruvaGraphMCPServer, StdioMCPTransport };
