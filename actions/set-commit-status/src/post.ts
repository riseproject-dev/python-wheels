import * as core from '@actions/core';
import { deriveJobState, isDispatch, parseInputs, setStatus } from './status';

async function run(): Promise<void> {
  if (!isDispatch()) {
    core.info(`Event is ${process.env.GITHUB_EVENT_NAME}, not workflow_dispatch; skipping.`);
    return;
  }
  const inputs = parseInputs();
  const state = await deriveJobState(inputs.token);
  await setStatus(inputs, state);
}

// Never fail the build just because we couldn't annotate the PR.
run().catch((err) =>
  core.warning(`Failed to set final status: ${err instanceof Error ? err.message : String(err)}`),
);
