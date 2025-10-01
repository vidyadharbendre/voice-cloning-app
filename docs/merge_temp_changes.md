# Merging Temporary Changes Back to `main`

Follow these steps to merge work that lives on a temporary branch (for example `work` or `feature/audio-fallbacks`) back into your primary branch, `main`, and push it to your remote repository.

1. **Commit your work on the temporary branch.**
   ```bash
   git status
   git add <files>
   git commit -m "Describe the work you finished"
   ```
2. **Switch to the `main` branch and update it.**
   ```bash
   git checkout main
   git pull origin main
   ```
3. **Merge the temporary branch into `main`.**
   Replace `work` with the name of your branch if it is different.
   ```bash
   git merge work
   ```
   Resolve any conflicts if Git reports them, then continue the merge:
   ```bash
   # after resolving conflicts
   git add <files>
   git commit
   ```
4. **Run your test suite (recommended).**
   ```bash
   pytest
   ```
5. **Push the updated `main` branch.**
   ```bash
   git push origin main
   ```

If you prefer a linear history, you can replace step 3 with a rebase (`git rebase main` while on your temporary branch) and then fast-forward `main` to the rebased branch. When collaborating, coordinate with your team before rewriting history.
