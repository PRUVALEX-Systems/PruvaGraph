# Clean Commit Graph Setup for PruvaGraph

This guide will help you set up a professional, clean, and enforced commit graph for the PruvaGraph repository. This ensures that every commit follows a strict convention, resulting in a beautiful `Git Graph` and automated changelogs.

## Step 1: Install Husky and Commitlint

We will install Husky (to manage git hooks) and Commitlint (to enforce the commit message format).
Run the following in your terminal at the project root:

```bash
npm install --save-dev husky @commitlint/cli @commitlint/config-conventional
npx husky install
```

## Step 2: Configure Commitlint

We have already created `commitlint.config.js` at the root of the project. It uses the conventional config but is tailored specifically for PruvaGraph's scopes (`cli`, `pipeline`, `compress`, `mcp`, `ui`, `core`, etc.).

## Step 3: Add Husky `commit-msg` Hook

We have already set up `.husky/commit-msg` to automatically run commitlint on your commit messages. If a commit format is wrong, it will be rejected instantly.

Make sure the hook is executable:
```bash
chmod +x .husky/commit-msg
```

## Step 4: Use the Git Commit Template

We have created a `.gitmessage` template. This template will automatically load in your editor when you type `git commit` (without the `-m` flag), guiding you to write perfect commits.

Configure git to use it globally for this repo:
```bash
git config commit.template .gitmessage
```

## Step 5: Add Retroactive Tags (Visual Win)

To make your Git Graph look amazing immediately without rewriting history, let's add retroactive tags to your major milestones. Run these commands on your recent commits (replace `<commit-hash>` with the actual hashes):

```bash
git tag -a v1.0.1 <commit-hash-for-1.0.1> -m "Release v1.0.1"
git tag -a v1.1.0 <commit-hash-for-1.1.0> -m "Release v1.1.0"
git tag -a v1.2.0 <commit-hash-for-1.2.0> -m "Release v1.2.0"
git push origin --tags
```
*Note: This is 100% safe. It just adds visual chips to your graph.*

## Step 6: Configure VS Code Git Graph Settings

To match the PRUVALEX brand colors and make the graph visually stunning:
1. Open VS Code Settings (`Ctrl+,`).
2. Search for `Git Graph: Commit Details View`.
3. Set **Graph Style** to `rounded`.
4. Set **Colors** to the PRUVALEX palette (Indigo & Green):
   - `#4F46E5` (Indigo)
   - `#10B981` (Emerald/Green)
   - `#6366F1`
   - `#34D399`

## Step 7: Optional Enhancements

### 1. GPG Signing (Verified Badge)
Sign your commits to get the green "Verified" badge on GitHub.
1. Generate a GPG key: `gpg --full-generate-key`
2. Tell Git to use it: `git config --global user.signingkey <YOUR_KEY_ID>`
3. Auto-sign commits: `git config --global commit.gpgsign true`
4. Add the public key to your GitHub Settings.

### 2. Auto-Changelog Generation
Since your commits are now conventional, you can auto-generate `CHANGELOG.md`!
```bash
npm install -g standard-version
standard-version
```

---

## 💡 Convention Reference Card

**Format:** `type(scope): subject`

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code restructuring (no new features/fixes)
- `perf`: Performance improvements
- `test`: Adding or fixing tests
- `chore`: Build tasks, package manager configs, etc.

**PruvaGraph Scopes:**
- `cli`: Command-line interface
- `pipeline`: Core graph building pipeline
- `mcp`: Claude Code MCP integration
- `compress`: Token compression layer (L5)
- `cache`: Hashing and global cache (L1, A5)
- `ui`: VS Code extension UI
- `docs`: Documentation files

## 🔄 Before / After Examples

Here are 5 examples of your past messy commits converted into the new clean format:

| Before (Messy) | After (Clean & Enforced) |
|---|---|
| `fixed the compression bug where it crashed` | `fix(compress): resolve crash during token reduction` |
| `added mcp server to connect with claude` | `feat(mcp): implement Claude Code MCP server` |
| `update readme with new cost model` | `docs(readme): update cost model with honest metrics` |
| `refactored pipeline to use updated config` | `refactor(pipeline): integrate updated build configuration` |
| `wired dead layers L5 N9 A5` | `feat(pipeline): integrate L5, N9, and A5 layers into graph extraction` |
