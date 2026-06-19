const fs = require('fs');
const path = require('path');

const extensionJsPath = path.join(__dirname, '..', 'extension', 'dist', 'extension.js');
const MAX_SIZE_MB = 5;

// Note: If extension.js isn't available yet during CI, we just skip it or warn
if (!fs.existsSync(extensionJsPath)) {
    console.log("⚠️ dist/extension.js not found. Skipping size check.");
    process.exit(0);
}

const stats = fs.statSync(extensionJsPath);
const sizeMB = stats.size / (1024 * 1024);

console.log(`🔍 Asserting performance contracts...`);
console.log(`   - File: ${extensionJsPath}`);
console.log(`   - Size: ${sizeMB.toFixed(2)} MB`);

if (sizeMB > MAX_SIZE_MB) {
    console.error(`❌ Contract failed: extension.js is ${sizeMB.toFixed(2)}MB (Limit is ${MAX_SIZE_MB}MB)`);
    process.exit(1);
}

console.log(`✅ All performance contracts passed.`);
process.exit(0);
