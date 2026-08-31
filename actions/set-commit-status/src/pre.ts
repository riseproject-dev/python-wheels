import * as core from '@actions/core';
import { isDispatch, parseInputs, setStatus } from './status';

async function run(): Promise<void> {
  if (!isDispatch()) {
    core.info(`Event is ${process.env.GITHUB_EVENT_NAME}, not workflow_dispatch; skipping.`);
    return;
  }
  await setStatus(parseInputs(), 'pending');
}

// Never fail the build just because we couldn't annotate the PR.
run().catch((err) =>
  core.warning(`Failed to set pending status: ${err instanceof Error ? err.message : String(err)}`),
);
