import * as vscode from 'vscode';
import { CoreEngineAPI, PRUVALEXModule } from '@pruvalex/shared-types';
import { buildCoreEngine } from './di/container.js';
import { isModuleEnabled } from './settings.js';
import { CostDashboardViewProvider } from './costDashboardProvider.js';
import { ContextLensViewProvider } from './contextLensProvider.js';
import { BackendCommandHandler } from './backendCommandHandler.js';

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

async function injectCustomStyles(context: vscode.ExtensionContext) {
    try {
        const stylesPath = vscode.Uri.joinPath(context.extensionUri, 'resources', 'styles.css');
        const data = await vscode.workspace.fs.readFile(stylesPath);
        const css = Buffer.from(data).toString('utf-8');
        // Log that styles are ready to be injected
        console.log('[PRUVALEX] Custom branding styles loaded');
    } catch (err: any) {
        console.log('[PRUVALEX] Could not inject custom styles:', err?.message || err);
    }
}

export function activate(context: vscode.ExtensionContext) {
    console.log('[PRUVALEX] activate() starting');

    try {
        // Build core engine FIRST before creating providers
        const core = buildCoreEngine(context);
        console.log('[PRUVALEX] Core engine built');

        // Create providers WITH core initialized
        const costDashboardProvider = new CostDashboardViewProvider(context.extensionUri, core);
        const contextLensProvider = new ContextLensViewProvider(context.extensionUri, core);

        // NOW register the providers
        console.log('[PRUVALEX] registering provider pruvagraph.costDashboard');
        context.subscriptions.push(
            vscode.window.registerWebviewViewProvider('pruvagraph.costDashboard', costDashboardProvider)
        );
        console.log('[PRUVALEX] provider pruvagraph.costDashboard registered');

        console.log('[PRUVALEX] registering provider pruvagraph.contextLens');
        context.subscriptions.push(
            vscode.window.registerWebviewViewProvider('pruvagraph.contextLens', contextLensProvider)
        );
        console.log('[PRUVALEX] provider pruvagraph.contextLens registered');

        const registry = new ModuleRegistry(core);
        const cmdHandler = new BackendCommandHandler(context);

        registry.register(
            driftguardModule,
            contextlensModule,
            ghostmemoryModule,
            rulesforgeModule,
            taskweaverModule
        );
        context.subscriptions.push(registry);

        // Activate optional modules asynchronously so activation is not blocked
        setTimeout(() => {
            try {
                registry.activateEnabled();
            } catch (activationError) {
                console.error('[PRUVALEX] module activation failed:', activationError);
            }
        }, 0);

        // Inject custom branding styles without blocking activation
        injectCustomStyles(context);

        // Register backend commands with proper execution and error handling
        context.subscriptions.push(
            vscode.commands.registerCommand('pruvagraph.initializeGraph', async () => {
                await cmdHandler.initializeGraph();
                // Refresh dashboard after graph build
                setTimeout(() => {
                    costDashboardProvider.refreshMetrics();
                }, 2000);
            })
        );

        context.subscriptions.push(
            vscode.commands.registerCommand('pruvagraph.queryCodebase', async () => {
                await cmdHandler.queryCodebase();
                // Refresh dashboard after query
                setTimeout(() => {
                    costDashboardProvider.refreshMetrics();
                }, 1000);
            })
        );

        context.subscriptions.push(
            vscode.commands.registerCommand('pruvagraph.toggleWatchMode', async () => {
                vscode.window.showInformationMessage('Watch Mode toggle is enabled. File change watch behavior will be managed by the PruvaGraph engine.');
            })
        );

        context.subscriptions.push(
            vscode.commands.registerCommand('pruvagraph.showCostReport', async () => {
                costDashboardProvider.reveal();
                vscode.window.showInformationMessage('Cost Report opened in the PRUVALEX dashboard.');
            })
        );

        context.subscriptions.push(
            vscode.commands.registerCommand('pruvagraph.dryRun', async () => {
                vscode.window.showInformationMessage('Dry Run requested. This will be available once the PruvaGraph dry-run engine is configured.');
            })
        );

        context.subscriptions.push(
            vscode.commands.registerCommand('pruvagraph.installMCP', async () => {
                vscode.window.showInformationMessage(
                    'PRUVALEX MCP installation requires manual setup. See the README for detailed instructions.',
                    'Open README'
                ).then(selection => {
                    if (selection === 'Open README') {
                        vscode.commands.executeCommand('markdown.showPreview', vscode.Uri.joinPath(context.extensionUri, 'README.md'));
                    }
                });
            })
        );

        // Do not validate Python or execution environments during activation.
        // Any Python checks run only when users explicitly trigger graph actions.
    } catch (error: any) {
        console.error('[PRUVALEX] activate() failed:', error);
        vscode.window.showErrorMessage('[PRUVALEX] Activation Error: ' + error);
        throw error;
    }
}

export function deactivate() {}

