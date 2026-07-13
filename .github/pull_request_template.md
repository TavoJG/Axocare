## Summary

- what changed
- why it changed

## Areas Touched

- [ ] Python backend (`api.py`, `control.py`, `axocare_api/`, `axocare_agent/`, `mcp_server/`, `tests/`, `migrations/`)
- [ ] Frontend (`frontend/`)
- [ ] Camera service (`camera_service/`)
- [ ] Health checker (`health_checker/`)
- [ ] Deployment or ops docs/config

## Hardware / Runtime Impact

- [ ] Affects Raspberry Pi GPIO, sensors, relay behavior, or camera streaming
- [ ] Requires config changes
- [ ] Requires migration changes
- [ ] No hardware or runtime behavior changes

Notes:

## Validation

- [ ] `pytest tests`
- [ ] `cd frontend && npm test`
- [ ] `cd frontend && npm run build`
- [ ] `cd camera_service && go test ./...`
- [ ] `cd health_checker && go test ./...`
- [ ] I did not run all relevant checks locally

Checks run:

## Frontend Build Output

- [ ] This PR does not change `frontend/`
- [ ] I rebuilt the frontend and committed the updated `frontend/dist` output

## Screenshots or API Examples

Include screenshots, curl output, or sample payloads when the UI or API behavior changed.

## Follow-up Notes

List any risks, TODOs, or manual verification steps for reviewers.
