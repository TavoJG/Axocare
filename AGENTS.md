# Project Instructions

## Required Checks

- Run the tests for each service you modify before finishing work.
- If you change Python backend code, run `pytest tests`.
- If you change `camera_service`, run `go test ./...` from `camera_service/`.
- If you change `health_checker`, run `go test ./...` from `health_checker/`.
- If you change frontend source or assets under `frontend/`, run `npm test` and `npm run build` from `frontend/`, then commit the updated `frontend/dist` output.

## Pull Requests

- Pull requests are expected to pass the matching service test workflow for the files they change.
- Pull requests that touch `frontend/` must keep the generated frontend build in `frontend/dist` up to date.
