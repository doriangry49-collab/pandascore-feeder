# pandascore-feeder

Note about Vercel configuration
--------------------------------

This repository uses an infra-as-code approach: `vercel.json` is the authoritative configuration for builds and cron jobs. When `vercel.json` contains build settings (for example the `builds` block) Vercel will prefer the repository configuration over the Project Settings in the Dashboard. That can cause the Dashboard to show a warning like:

"Configuration Settings in the current Production deployment differ from your current Project Settings."

What this means for you:
- If you want repo-driven, repeatable deployments, keep `vercel.json` in the repo and manage builds/crons there.
- If you prefer Dashboard-managed builds, remove or simplify `vercel.json` (for example remove the `builds` block) and deploy.

Cron note:
- Hobby (free) Vercel plans limit cron frequency. Hourly cron requires Pro. The current `vercel.json` in this repo uses a daily cron (`0 0 * * *`) to remain compatible with Hobby accounts.

If you want me to switch to Dashboard-managed settings instead, say so and I'll remove the conflicting fields from `vercel.json` and push the change.