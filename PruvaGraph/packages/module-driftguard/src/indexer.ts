import { IWorkspaceContext } from '@pruvalex/shared-types';
import { DriftGuardRepository } from './repository.js';
import * as vscode from 'vscode';

export class DriftGuardIndexer {
    constructor(private context: IWorkspaceContext, private repo: DriftGuardRepository) {
        this.context.onFileChanged((uri: vscode.Uri) => {
            if (uri.fsPath.endsWith('package.json') || uri.fsPath.includes('node_modules')) {
                this.reindex();
            }
        });
        
        this.reindex();
    }

    private reindex() {
        const manifest = this.context.getPackageManifest();
        if (!manifest || !manifest.dependencies) return;

        // Stub logic for indexing node_modules/**/*.d.ts
        // A full AST parser would be heavy. We'll simulate finding symbols for now.
        for (const pkg of Object.keys(manifest.dependencies)) {
            const version = manifest.dependencies[pkg];
            const id = `${pkg}:someMethod`;
            this.repo.upsertSymbol(id, 'someMethod', pkg, 'someMethod(): void', version, 'someMethod(): void');
            const deprecatedId = `${pkg}:deprecatedMethod`;
            this.repo.upsertSymbol(deprecatedId, 'deprecatedMethod', pkg, 'deprecatedMethod(): void // DEPRECATED', version, 'deprecatedMethod(): void // DEPRECATED');
        }
    }
}

