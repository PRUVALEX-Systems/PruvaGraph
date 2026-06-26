/**
 * Test Runner for @vscode/test-electron
 *
 * WINDOWS PATH BUG (DEP0190):
 * @vscode/test-electron uses child_process.spawn with shell:true to launch VS
 * Code, concatenating all CLI args unsafely. Both --extensionDevelopmentPath
 * and --extensionTestsPath arguments are subject to space-truncation.
 *
 * Fix: create a directory junction (mklink /J) at a space-free path for the
 * extension root, and copy the test file to a space-free temp directory.
 * Junctions work without admin on Windows (unlike symlinks).
 */

const path  = require('path');
const fs    = require('fs');
const os    = require('os');
const cp    = require('child_process');
const { runTests } = require('@vscode/test-electron');

async function main() {
  const projectRoot = path.resolve(__dirname, '..');
  const tmpDir = path.join(os.tmpdir(), 'pg' + Date.now()); // short, no spaces
  fs.mkdirSync(tmpDir, { recursive: true });

  // 1. Create a junction (no admin required on Windows) to the project root
  //    at a space-free path.
  const extLinkPath = path.join(tmpDir, 'ext');
  try {
    cp.execSync(`cmd /c mklink /J "${extLinkPath}" "${projectRoot}"`, { stdio: 'pipe' });
  } catch {
    // Fallback: if junction fails (non-Windows or permission issue), use the
    // original path. Tests may fail if the path has spaces.
    console.warn('[runTest] Warning: Could not create junction — using original path (may fail with spaces)');
    fs.mkdirSync(extLinkPath, { recursive: true });
  }

  // 2. Copy commands.test.js to the space-free temp directory
  const srcTest = path.resolve(__dirname, 'extension', 'commands.test.js');
  const dstTest = path.join(tmpDir, 'commands.test.js');
  fs.copyFileSync(srcTest, dstTest);

  // 3. Minimal workspace (space-free)
  const testWorkspace = path.join(tmpDir, 'ws');
  fs.mkdirSync(testWorkspace, { recursive: true });
  fs.writeFileSync(path.join(testWorkspace, 'test.py'), '# Test\nprint("hello")');
  fs.writeFileSync(path.join(testWorkspace, 'test.js'), '// Test\nconsole.log("hello");');

  console.log('[runTest] extensionDevelopmentPath (junction):', extLinkPath);
  console.log('[runTest] extensionTestsPath (no-space):', dstTest);
  console.log('[runTest] testWorkspace:', testWorkspace);

  try {
    // Isolated user-data-dir: prevents mutex collision with a running VS Code instance.
    // Without this, @vscode/test-electron fights for the same global mutex lock and
    // the extension host shuts down immediately without running any tests.
    const testUserDataDir = path.join(tmpDir, 'userdata');
    fs.mkdirSync(testUserDataDir, { recursive: true });

    await runTests({
      extensionDevelopmentPath: extLinkPath, // ← space-free via junction
      extensionTestsPath: dstTest,           // ← space-free via copy
      launchArgs: [
        testWorkspace,
        `--user-data-dir=${testUserDataDir}`, // ← isolated mutex, isolated profile
        '--disable-extensions',               // ← skip marketplace extensions, faster boot
        '--no-sandbox',                       // ← required in some CI/headless envs
      ],
      extensionTestsEnv: {
        // Tell commands.test.js where the real project root is for mocha resolution
        PRUVAGRAPH_PROJECT_ROOT: projectRoot,
      },
    });
  } finally {
    // Cleanup (best-effort — junction deletion may need a moment)
    setTimeout(() => {
      try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch {}
    }, 1000);
  }
}

main().catch(err => {
  console.error('Failed to run extension host tests:', err.message);
  process.exit(1);
});
