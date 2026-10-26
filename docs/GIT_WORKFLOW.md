# Git Workflow

```
main  ●───────────────────────────●────────────────●   (v0.9 pilot, v1.0 final)
       \                         /                /
dev     ●──●────●─────●────●────●──────●─────●───●     (integration, always green)
            \  /     /    /             \   /
ronit        ●●─────●────●               ●─●           (Ronit's work)
              \         /
mit            ●──●────●                               (Mit's work)
```

## Rules

1. **Never commit directly to `main` or `dev`.** Only PRs.
2. Work on your own branch: `ronit` or `mit`. For bigger tasks you may create
   short-lived branches off it (e.g. `ronit-r2-bkt`; git cannot have both `ronit` and `ronit/...`) and merge them back into
   `ronit`.
3. **Sync often:** at least every Friday, and before opening a PR, run
   ```bash
   git checkout ronit            # or mit
   git fetch origin
   git merge origin/dev          # merge, don't rebase a shared branch
   # fix conflicts, run tests
   git push origin ronit
   ```
4. **PR into `dev`:**
   - title `[R2] BKT mastery model` (task ID first);
   - fill in the PR template;
   - the *other* person reviews;
   - CI must be green.
5. **Release PR `dev → main`:** only at milestones (v0.9 after week 8, v1.0
   after week 12, plus hotfixes). Both approve. Tag the merge commit
   (`git tag v0.9 && git push origin v0.9`).
6. **Contract changes** (anything in `backend/app/contracts/`) go in a
   separate small PR labelled `contract` that both approve. Never bundle them
   with feature work.
7. **Commit messages:** `R2: add BKT observation update` (task ID +
   imperative). One logical change per commit.
8. **Never commit secrets.** Use `.env` (git-ignored). `.env.example` lists
   the variable names.

## One-time GitHub setup (repo owner, about 5 minutes)

In **Settings → Branches → Add branch ruleset**:

- `main`:
  - require a pull request (1 approval);
  - require the `ci` status checks to pass;
  - block force pushes and deletions.
- `dev`: the same rules.
- **Settings → General:** set the default branch to `dev`, so new PRs target
  it automatically.
- Add Mit as a collaborator with **Write** access.
- In `.github/CODEOWNERS`, fill in Mit's GitHub username.
