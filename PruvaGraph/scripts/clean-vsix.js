const fs = require('fs');
const path = require('path');

// Clean any old .vsix in this package root to avoid stale artifacts
const rootDir = path.resolve(__dirname, '..');
try {
  const files = fs.readdirSync(rootDir);
  files.forEach(file => {
    if (file.endsWith('.vsix')) {
      console.log(`Deleting old VSIX: ${file}`);
      fs.unlinkSync(path.join(rootDir, file));
    }
  });
  console.log('Cleaned old .vsix files (if any).');
} catch (err) {
  // Non-fatal — just log and continue the build
  console.warn('clean-vsix: could not clean .vsix files:', err.message);
}
