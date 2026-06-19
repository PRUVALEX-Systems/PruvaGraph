import * as vscode from 'vscode';
import { PRUVALEXEventMap, IEventBus } from './events.js';

export interface ModuleRepository {
  run(sql: string, ...params: unknown[]): { changes: number; lastInsertRowid: number | bigint };
  get<T = Record<string, unknown>>(sql: string, ...params: unknown[]): T | undefined;
  all<T = Record<string, unknown>>(sql: string, ...params: unknown[]): T[];
}

export interface IGraphStore {
  scope(modulePrefix: string): ModuleRepository;
  migrate(): void;
}

export interface IGraphStoreInternal extends IGraphStore {
  _internalExec(sql: string): void;
  _internalQuery<T>(sql: string, ...params: unknown[]): T[];
}

export interface IMCPTransport {
  call(server: string, tool: string, args: unknown): Promise<unknown>;
  registerTool(toolName: string, handler: (args: unknown) => Promise<unknown>): void;
}

export interface PackageJson {
    dependencies?: Record<string, string>;
    devDependencies?: Record<string, string>;
}

export interface TypeDeclarationIndex {
    // Abstract index representation
}

export interface Tree {
    rootNode: {
        type: string;
        text: string;
        children: any[];
        descendantsOfType(type: string): any[];
    } | null;
    isAvailable: boolean;
}

export interface IWorkspaceContext {
  getPackageManifest(): PackageJson;
  getInstalledTypes(pkg: string): TypeDeclarationIndex;
  getAST(uri: vscode.Uri): Tree;
  onFileChanged: vscode.Event<vscode.Uri>;
}

export interface WebviewHost {
    registerPanel(id: string, title: string, options?: vscode.WebviewPanelOptions): vscode.WebviewPanel | undefined;
    getPanel(id: string): vscode.WebviewPanel | undefined;
    disposePanel(id: string): void;
}

export interface CoreEngineAPI {
  db: IGraphStore;
  mcp: IMCPTransport;
  workspace: IWorkspaceContext;
  events: IEventBus<PRUVALEXEventMap>;
  webview: WebviewHost;
}

export interface PRUVALEXModule {
  readonly id: 'driftguard' | 'contextlens' | 'ghostmemory' | 'rulesforge' | 'taskweaver';
  activate(deps: CoreEngineAPI): vscode.Disposable;
}
