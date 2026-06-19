import * as vscode from 'vscode';
import { CoreEngineAPI, PRUVALEXModule } from '@pruvalex/shared-types';
import { buildCoreEngine } from './di/container.js';
import { isModuleEnabled } from './settings.js';

import { driftguardModule } from '@pruvalex/module-driftguard';
import { contextlensModule } from '@pruvalex/module-contextlens';
import { ghostmemoryModule } from '@pruvalex/module-ghostmemory';
import { rulesforgeModule } from '@pruvalex/module-rulesforge';
import { taskweaverModule } from '@pruvalex/module-taskweaver';

class ModuleRegistry implements vscode.Disposable {
    private core: CoreEngineAPI;
    private modules: PRUVALEXModule[] = [];
    private activeDisposables: Map<string, vscode.Disposable> = new Map();
    private configListener: vscode.Disposable;

    constructor(core: CoreEngineAPI) {
        this.core = core;
        // Watch for settings changes
        this.configListener = vscode.workspace.onDidChangeConfiguration(e => {
            if (e.affectsConfiguration('pruvagraph.modules')) {
                this.reconcileModules();
            }
        });
    }

    register(...modules: PRUVALEXModule[]) {
        this.modules.push(...modules);
    }

    activateEnabled() {
        this.reconcileModules();
    }

    private reconcileModules() {
        for (const mod of this.modules) {
            const shouldBeActive = isModuleEnabled(mod.id);
            const isActive = this.activeDisposables.has(mod.id);

            if (shouldBeActive && !isActive) {
                // Activate module
                console.log(`[PRUVALEX] Activating module: ${mod.id}`);
                const disposable = mod.activate(this.core);
                this.activeDisposables.set(mod.id, disposable);
            } else if (!shouldBeActive && isActive) {
                // Deactivate module
                console.log(`[PRUVALEX] Deactivating module: ${mod.id}`);
                this.activeDisposables.get(mod.id)!.dispose();
                this.activeDisposables.delete(mod.id);
            }
        }
    }

    dispose() {
        for (const [, disposable] of this.activeDisposables) {
            disposable.dispose();
        }
        this.activeDisposables.clear();
        this.configListener.dispose();
    }
}

export function activate(context: vscode.ExtensionContext) {
    const core = buildCoreEngine(context);
    const registry = new ModuleRegistry(core);
    registry.register(
        driftguardModule,
        contextlensModule,
        ghostmemoryModule,
        rulesforgeModule,
        taskweaverModule
    );
    registry.activateEnabled();
    context.subscriptions.push(registry);

    context.subscriptions.push(vscode.commands.registerCommand('pruvagraph.initializeGraph', () => {
        const workspace = core.workspace as any;
        if (workspace.runner) {
            workspace.runner.ensureGraph();
        } else {
            vscode.window.showErrorMessage('PRUVALEX: Workspace runner not initialized.');
        }
    }));
}

export function deactivate() {}

