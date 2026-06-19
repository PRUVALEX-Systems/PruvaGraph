import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { IWorkspaceContext, PackageJson, TypeDeclarationIndex, Tree } from '@pruvalex/shared-types';
import { PruvaGraphRunner } from '../runner.js';

export class WorkspaceContext implements IWorkspaceContext {
    private fileWatcher: vscode.FileSystemWatcher | null = null;
    private fileChangedEmitter = new vscode.EventEmitter<vscode.Uri>();
    public readonly onFileChanged = this.fileChangedEmitter.event;

    private astCache = new Map<string, Tree>();
    public runner: PruvaGraphRunner | null = null;

    constructor(private extensionPath: string = '') {
        if (vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0) {
            const rootPath = vscode.workspace.workspaceFolders[0].uri.fsPath;
            this.fileWatcher = vscode.workspace.createFileSystemWatcher('**/*');
            this.fileWatcher.onDidChange(uri => this.fileChangedEmitter.fire(uri));
            this.fileWatcher.onDidCreate(uri => this.fileChangedEmitter.fire(uri));
            this.fileWatcher.onDidDelete(uri => {
                this.astCache.delete(uri.toString());
                this.fileChangedEmitter.fire(uri);
            });

            this.runner = new PruvaGraphRunner(rootPath, this.extensionPath);
            this.runner.ensureGraph().catch(console.error);
        }
    }

    getPackageManifest(): PackageJson {
        if (!vscode.workspace.workspaceFolders || vscode.workspace.workspaceFolders.length === 0) {
            return {};
        }
        const rootPath = vscode.workspace.workspaceFolders[0].uri.fsPath;
        const pkgPath = path.join(rootPath, 'package.json');
        try {
            if (fs.existsSync(pkgPath)) {
                return JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
            }
        } catch (e) {
            console.error('Failed to parse package.json', e);
        }
        return {};
    }

    getInstalledTypes(pkg: string): TypeDeclarationIndex {
        return {} as TypeDeclarationIndex;
    }

    getAST(uri: vscode.Uri): Tree {
        const cached = this.astCache.get(uri.toString());
        if (cached) return cached;

        // Check if tree-sitter is available
        try {
            // Dynamic import — only works if tree-sitter optional deps are installed
            // For now: return a minimal stub that signals unavailability
            const stub: Tree = {
                rootNode: null,
                isAvailable: false
            };
            this.astCache.set(uri.toString(), stub);
            return stub;
        } catch (e) {
            return { rootNode: null, isAvailable: false };
        }
    }

    dispose() {
        this.fileWatcher?.dispose();
        this.fileChangedEmitter.dispose();
    }
}

