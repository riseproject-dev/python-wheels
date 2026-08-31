import * as core from '@actions/core';
import * as github from '@actions/github';

// The four states a GitHub commit status can hold.
export type CommitState = 'error' | 'failure' | 'pending' | 'success';

export interface Inputs {
  token: string;
  context: string;
  sha: string;
  targetUrl?: string;
  description?: string;
}

// This action only makes sense for workflow_dispatch runs (builds kicked off by
// pr-trigger.yml). The step-level `if:` in the workflow already guards this, but
// pre/post hooks run per pre-if/post-if (default always()) which a step `if:`
// does not reliably suppress — so we re-check here as the authoritative gate.
export function isDispatch(): boolean {
  return process.env.GITHUB_EVENT_NAME === 'workflow_dispatch';
}

export function parseInputs(): Inputs {
  const sha = core.getInput('sha') || process.env.GITHUB_SHA || '';
  if (!sha) {
    throw new Error('Cannot determine commit SHA: no `sha` input and GITHUB_SHA is unset.');
  }
  return {
    token: core.getInput('token', { required: true }),
    context: core.getInput('context', { required: true }),
    sha,
    targetUrl: core.getInput('target-url') || defaultTargetUrl(),
    description: core.getInput('description') || undefined,
  };
}

// Link the status back to this workflow run when the caller didn't supply a URL.
function defaultTargetUrl(): string | undefined {
  const server = process.env.GITHUB_SERVER_URL;
  const repo = process.env.GITHUB_REPOSITORY;
  const runId = process.env.GITHUB_RUN_ID;
  return server && repo && runId
    ? `${server}/${repo}/actions/runs/${runId}`
    : undefined;
}

export async function setStatus(inputs: Inputs, state: CommitState): Promise<void> {
  const octokit = github.getOctokit(inputs.token);
  const { owner, repo } = github.context.repo;
  core.info(`Setting ${state} status "${inputs.context}" on ${owner}/${repo}@${inputs.sha}`);
  await octokit.rest.repos.createCommitStatus({
    owner,
    repo,
    sha: inputs.sha,
    state,
    target_url: inputs.targetUrl,
    description: inputs.description,
    context: inputs.context,
  });
}

// A post hook can't be handed ${{ job.status }}, so it derives the outcome itself:
// query this run's jobs and inspect our own job's finished step conclusions. Our
// job is the in_progress one on this runner (a runner executes one job at a time,
// and our post step is what's keeping it in_progress). Steps still running
// (conclusion === null) — notably the post steps themselves — are ignored.
export async function deriveJobState(token: string): Promise<CommitState> {
  const octokit = github.getOctokit(token);
  const { owner, repo } = github.context.repo;
  const runnerName = process.env.RUNNER_NAME;

  const jobs = await octokit.paginate(octokit.rest.actions.listJobsForWorkflowRun, {
    owner,
    repo,
    run_id: github.context.runId,
    filter: 'latest',
    per_page: 100,
  });

  const ours = jobs.find(
    (job) => job.status === 'in_progress' && job.runner_name === runnerName,
  );
  if (!ours) {
    core.warning(
      `Could not identify this job (runner "${runnerName}") among ${jobs.length} jobs; reporting error.`,
    );
    return 'error';
  }

  let sawFailure = false;
  let sawError = false;
  for (const step of ours.steps ?? []) {
    switch (step.conclusion) {
      case 'failure':
      case 'action_required':
        sawFailure = true;
        break;
      case 'cancelled':
      case 'timed_out':
      case 'stale':
        sawError = true;
        break;
      default:
        break;
    }
  }
  return sawFailure ? 'failure' : sawError ? 'error' : 'success';
}
