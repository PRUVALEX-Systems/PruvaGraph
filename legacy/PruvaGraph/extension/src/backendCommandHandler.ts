import * as vscode from 'vscode';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export class BackendCommandHandler {
    private terminal: vscode.Terminal | undefined;

    constructor(private context: vscode.ExtensionContext) {}

    /**
     * Execute the PruvaGraph CLI to build the knowledge graph
     */
    async initializeGraph(): Promise<void> {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            vscode.window.showErrorMessage('PRUVALEX: No workspace folder is open. Please open a folder first.');
            return;
        }

        const workspacePath = workspaceFolders[0].uri.fsPath;

        try {
            const pythonCommand = await this.resolvePythonExecutable(workspacePath);
            const command = `${pythonCommand} -m pruvagraph.cli .`;

            this.showExecutionTerminal(workspacePath, command);

            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: 'Building PRUVALEX Knowledge Graph...',
                    cancellable: false
                },
                async (progress) => {
                    progress.report({ increment: 0 });

                    const { stdout, stderr } = await execAsync(command, {
                        cwd: workspacePath,
                        shell: this.getShellExecutable(),
                        timeout: 10 * 60 * 1000,
                        maxBuffer: 50 * 1024 * 1024
                    });

                    progress.report({ increment: 100 });

                    if (stdout) {
                        console.log('[PRUVALEX] initializeGraph stdout:', stdout);
                    }
                    if (stderr) {
                        console.warn('[PRUVALEX] initializeGraph stderr:', stderr);
                    }
                }
            );

            vscode.window.showInformationMessage(
                '✅ PRUVALEX Graph Built Successfully!',
                'Open Dashboard'
            ).then(selection => {
                if (selection === 'Open Dashboard') {
                    vscode.commands.executeCommand('pruvagraph.costDashboard.focus');
                }
            });
        } catch (error: any) {
            const errorMsg = error?.stderr || error?.message || String(error);
            vscode.window.showErrorMessage(`❌ Graph Build Failed: ${errorMsg}`);
            console.error('[PRUVALEX] Graph build error:', error);
        }
    }

    /**
     * Execute import validation and get detailed analysis
     */
    async queryCodebase(): Promise<void> {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            vscode.window.showErrorMessage('PRUVALEX: No workspace folder is open.');
            return;
        }

        const workspacePath = workspaceFolders[0].uri.fsPath;

        try {
            const pythonCommand = await this.resolvePythonExecutable(workspacePath);
            const command = `${pythonCommand} -m pruvagraph.cli --validate "${workspacePath}"`;
            this.showExecutionTerminal(workspacePath, command);

            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Window,
                    title: 'Querying Codebase...',
                    cancellable: false
                },
                async (progress) => {
                    progress.report({ increment: 0 });

                    const { stdout, stderr } = await execAsync(command, {
                        cwd: workspacePath,
                        shell: this.getShellExecutable(),
                        timeout: 10 * 60 * 1000,
                        maxBuffer: 50 * 1024 * 1024
                    });

                    progress.report({ increment: 100 });

                    if (stdout) {
                        console.log('[PRUVALEX] queryCodebase stdout:', stdout);
                    }
                    if (stderr) {
                        console.warn('[PRUVALEX] queryCodebase stderr:', stderr);
                    }

                    vscode.window.showInformationMessage('✅ Codebase Query Complete!');
                }
            );
        } catch (error: any) {
            const errorMsg = error?.stderr || error?.message || String(error);
            vscode.window.showErrorMessage(`❌ Query Failed: ${errorMsg}`);
            console.error('[PRUVALEX] Codebase query error:', error);
        }
    }

    /**
     * Check if Python and pruvagraph are installed
     */
    async validateEnvironment(): Promise<boolean> {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        const workspacePath = workspaceFolders && workspaceFolders[0]?.uri.fsPath;

        try {
            const pythonCommand = await this.resolvePythonExecutable(workspacePath);
            const { stdout: pythonVersion } = await execAsync(`${pythonCommand} --version`, {
                cwd: workspacePath,
                shell: this.getShellExecutable(),
                timeout: 15 * 1000,
                maxBuffer: 10 * 1024 * 1024
            });
            console.log('[PRUVALEX] Python version:', pythonVersion.trim());

            try {
                const { stdout: pruvagraphVer } = await execAsync(`${pythonCommand} -m pruvagraph --version`, {
                    cwd: workspacePath,
                    shell: this.getShellExecutable(),
                    timeout: 15 * 1000,
                    maxBuffer: 10 * 1024 * 1024
                });
                console.log('[PRUVALEX] PruvaGraph version:', pruvagraphVer.trim());
                return true;
            } catch (error) {
                console.warn('[PRUVALEX] PruvaGraph not found, will attempt install on demand', error);
                return true;
            }
        } catch (error) {
            console.error('[PRUVALEX] Python not found:', error);
            return false;
        }
    }

    private async resolvePythonExecutable(workspacePath?: string): Promise<string> {
        const candidates = ['python3', 'python', 'py -3'];

        for (const candidate of candidates) {
            try {
                const { stdout } = await execAsync(`${candidate} --version`, {
                    cwd: workspacePath,
                    shell: this.getShellExecutable(),
                    timeout: 15 * 1000,
                    maxBuffer: 10 * 1024 * 1024
                });
                if (stdout && /Python\s+[3-9]/i.test(stdout)) {
                    return candidate;
                }
            } catch {
                continue;
            }
        }

        throw new Error('Executable python3/python not found on PATH. Please install Python 3 and ensure it is available in your shell.');
    }

    private showExecutionTerminal(workspacePath: string, command: string) {
        if (!this.terminal || this.terminal.exitStatus !== undefined) {
            this.terminal = vscode.window.createTerminal('PRUVALEX Graph');
        }
        this.terminal.show(false);
        this.terminal.sendText(`cd "${workspacePath}"`, true);
        this.terminal.sendText(command, true);
    }

    private getShellExecutable(): string {
        return process.platform === 'win32' ? 'cmd.exe' : '/bin/sh';
    }

    /**
     * Dispose resources
     */
    dispose(): void {
        // Terminal is managed by VS Code
    }
}
