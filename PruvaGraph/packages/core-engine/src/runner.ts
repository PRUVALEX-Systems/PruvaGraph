import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

export class PruvaGraphRunner {
    private outputChannel: vscode.OutputChannel;
    private workspaceRoot: string;
    private extensionPath: string;

    constructor(workspaceRoot: string, extensionPath: string = '') {
        this.workspaceRoot = workspaceRoot;
        this.extensionPath = extensionPath;
        this.outputChannel = vscode.window.createOutputChannel('PruvaGraph Engine');
    }

    public async ensureGraph(): Promise<void> {
        return vscode.window.withProgress({
            location: vscode.ProgressLocation.Window,
            title: "Initializing PruvaGraph Knowledge...",
            cancellable: false
        }, async (progress) => {
            try {
                this.outputChannel.show(true);
                this.outputChannel.appendLine('[PruvaGraph] Checking Python environment...');
                
                const pythonExe = await this.findPython();
                if (!pythonExe) {
                    throw new Error('Python 3.10+ not found on system PATH.');
                }

                const venvPath = path.join(this.workspaceRoot, '.venv_pruvagraph');
                const venvPython = process.platform === 'win32' 
                    ? path.join(venvPath, 'Scripts', 'python.exe')
                    : path.join(venvPath, 'bin', 'python');

                if (!fs.existsSync(venvPath)) {
                    this.outputChannel.appendLine('[PruvaGraph] Creating isolated virtual environment...');
                    progress.report({ message: 'Creating virtual environment...' });
                    await this.execPromise(`"${pythonExe}" -m venv "${venvPath}"`);
                }

                // Search for python backend in priority order:
                const pythonSrcCandidates = [
                    path.join(this.extensionPath, 'python'),          // Bundled in extension
                    path.join(this.workspaceRoot, 'python'),          // In user's workspace (dev mode)
                    path.join(this.workspaceRoot, 'node_modules', '.pruvagraph', 'python'), // npm install
                ];
                
                const pruvagraphSrc = pythonSrcCandidates.find(p => fs.existsSync(p));
                
                if (pruvagraphSrc) {
                    this.outputChannel.appendLine('[PruvaGraph] Installing/Updating PruvaGraph engine...');
                    progress.report({ message: 'Installing dependencies...' });
                    await this.execPromise(`"${venvPython}" -m pip install -e "${pruvagraphSrc}" --quiet`);
                } else {
                    // Try installing from PyPI as fallback
                    this.outputChannel.appendLine('[PruvaGraph] Installing pruvagraph from PyPI...');
                    progress.report({ message: 'Installing dependencies from PyPI...' });
                    await this.execPromise(`"${venvPython}" -m pip install pruvagraph --quiet`);
                }

                this.outputChannel.appendLine('[PruvaGraph] Running graph extraction...');
                progress.report({ message: 'Parsing codebase (100% Local)...' });
                await this.execPromise(`"${venvPython}" -m pruvagraph.cli .`);

                this.outputChannel.appendLine('[PruvaGraph] Graph extraction complete!');
                vscode.window.showInformationMessage('PruvaGraph: Knowledge Graph is ready!');
            } catch (err: any) {
                this.outputChannel.appendLine(`[PruvaGraph ERROR] ${err.message}`);
                vscode.window.showErrorMessage('PruvaGraph Failed: Check output channel for details.');
            }
        });
    }

    private async findPython(): Promise<string | null> {
        const cmds = process.platform === 'win32' ? ['python', 'py -3'] : ['python3', 'python'];
        for (const cmd of cmds) {
            try {
                await this.execPromise(`${cmd} --version`);
                return cmd; // Found a working python
            } catch (e) {
                // Ignore and try next
            }
        }
        return null;
    }

    private execPromise(command: string): Promise<string> {
        return new Promise((resolve, reject) => {
            cp.exec(command, { cwd: this.workspaceRoot }, (error, stdout, stderr) => {
                if (stdout) this.outputChannel.append(stdout);
                if (stderr) this.outputChannel.append(stderr);
                
                if (error) {
                    reject(new Error(stderr || stdout || error.message));
                    return;
                }
                resolve(stdout);
            });
        });
    }
}
