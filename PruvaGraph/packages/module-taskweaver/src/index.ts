import * as vscode from 'vscode';
import { PRUVALEXModule, CoreEngineAPI } from '@pruvalex/shared-types';
import { TaskWeaverRepository } from './repository.js';
import * as crypto from 'crypto';
import * as cp from 'child_process';

function execAsync(cmd: string, cwd: string): Promise<string> {
    return new Promise((resolve, reject) => {
        cp.exec(cmd, { cwd }, (err, stdout, stderr) => {
            if (err) reject(new Error(stderr || err.message));
            else resolve(stdout);
        });
    });
}

export const taskweaverModule: PRUVALEXModule = {
    id: 'taskweaver',
    activate(deps: CoreEngineAPI): vscode.Disposable {
        const repo = new TaskWeaverRepository(deps.db);

        deps.mcp.registerTool('create_checkpoint', async (args: any) => {
            const { task_id, files_changed, git_sha } = args as { task_id: string, files_changed: string[], git_sha: string };
            const id = crypto.randomUUID();
            // Use commit_sha for commit_sha, and git_sha for git_sha
            repo.insertCheckpoint(id, task_id, files_changed || [], git_sha || 'unknown', git_sha || 'unknown');
            return { id, status: 'checkpoint saved' };
        });

        deps.mcp.registerTool('rollback_to_checkpoint', async (args: any) => {
            const { id } = args as { id: string };
            const checkpoint = repo.getCheckpointById(id);
            if (!checkpoint) {
                return { success: false, error: `Checkpoint ${id} not found` };
            }

            const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
            if (!workspaceRoot) {
                return { success: false, error: 'No workspace open' };
            }

            try {
                // Verify the commit exists
                await execAsync(`git cat-file -t ${checkpoint.commit_sha}`, workspaceRoot);
                // Perform the rollback
                await execAsync(`git checkout ${checkpoint.commit_sha} -- .`, workspaceRoot);
                
                deps.events.emit('checkpoint:created', {
                    taskId: checkpoint.task_id,
                    files: JSON.parse(checkpoint.files_changed)
                });
                
                return { success: true, restoredTo: checkpoint.commit_sha };
            } catch (err: any) {
                return { success: false, error: err.message };
            }
        });

        deps.mcp.registerTool('get_task_progress', async (args: any) => {
            const { task_id } = args as { task_id: string };
            const checkpoints = repo.getCheckpoints(task_id);
            return { 
                checkpoints: checkpoints.map(c => ({...c, files_changed: JSON.parse(c.files_changed)}))
            };
        });

        return {
            dispose: () => {}
        };
    }
};

