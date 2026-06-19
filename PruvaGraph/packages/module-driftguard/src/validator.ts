import * as vscode from 'vscode';
import { DriftGuardRepository } from './repository.js';
import { IEventBus, PRUVALEXEventMap, IWorkspaceContext } from '@pruvalex/shared-types';

export class DriftGuardValidator {
    private diagnosticCollection: vscode.DiagnosticCollection;

    constructor(
        private repo: DriftGuardRepository,
        private workspace: IWorkspaceContext,
        private events: IEventBus<PRUVALEXEventMap>
    ) {
        this.diagnosticCollection = vscode.languages.createDiagnosticCollection('driftguard');
    }

    validateDocument(document: vscode.TextDocument) {
        const diagnostics: vscode.Diagnostic[] = [];
        const text = document.getText();
        const tree = this.workspace.getAST(document.uri);
        if (!tree.isAvailable) {
            console.log('[DriftGuard] Tree-sitter not available — using regex-based drift detection');
        }

        // Parse import statements (TypeScript/JavaScript)
        // Pattern: import { Foo, Bar } from 'package-name'
        const importRegex = /import\s*\{([^}]+)\}\s*from\s*['"]([^'"]+)['"]/g;
        let match: RegExpExecArray | null;

        while ((match = importRegex.exec(text)) !== null) {
            const symbols = match[1].split(',').map(s => s.trim().split(' as ')[0].trim());
            const pkg = match[2];

            for (const sym of symbols) {
                if (!sym) continue;
                const known = this.repo.getSymbol(pkg, sym);
                if (known === undefined && !pkg.startsWith('.')) {
                    // Symbol not in our index AND not a relative import
                    const symIdx = text.indexOf(sym, match.index);
                    const pos = document.positionAt(symIdx);
                    const range = new vscode.Range(pos, pos.translate(0, sym.length));
                    const diag = new vscode.Diagnostic(
                        range,
                        `DriftGuard: Symbol '${sym}' from '${pkg}' not found in installed packages.`,
                        vscode.DiagnosticSeverity.Warning
                    );
                    diag.source = 'DriftGuard';
                    diagnostics.push(diag);

                    // Emit drift event for cross-module communication
                    this.events.emit('drift:detected', {
                        uri: document.uri.toString(),
                        symbol: sym,
                        reason: `Symbol not found in driftguard_index for package '${pkg}'`
                    });
                }
            }
        }

        this.diagnosticCollection.set(document.uri, diagnostics);
    }

    dispose() {
        this.diagnosticCollection.dispose();
    }
}

