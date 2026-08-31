import * as core from '@actions/core';

// JS actions require a `main` entry point. All the work happens in the pre
// (pending) and post (final outcome) hooks; main only exists to satisfy the
// runtime and to make the run visible in the log.
async function run(): Promise<void> {
  if (process.env.GITHUB_EVENT_NAME === 'workflow_dispatch') {
    core.info('Commit-status tracking active; final status will be set in the post step.');
  }
}

run().catch((err) =>
  core.warning(err instanceof Error ? err.message : String(err)),
);
