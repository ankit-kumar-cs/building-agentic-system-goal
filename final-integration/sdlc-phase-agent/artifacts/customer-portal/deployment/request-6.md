# Deployment Checklist

Feature: Deploy the feedback service to production

Date: 2026-10-17

Client: Acme | Project: Customer Portal

## Description:

Deploy the feedback service to production

## Checklist:

- [ ] Pull the latest `feedback-service` code from the `main` branch and verify the commit hash.
- [ ] Run the full test suite (`npm test` / `pytest`) and ensure all tests pass before building.
- [ ] Build the Docker image (`docker build -t feedback-service:${TAG} .`) and run static analysis checks.
- [ ] Push the Docker image to the production registry (`docker push feedback-service:${TAG}`).
- [ ] Update the Kubernetes deployment manifest to use the new image tag and apply the changes (`kubectl apply -f k8s/feedback-service.yaml`).
- [ ] Execute any required database migrations (`./migrate.sh --env=prod`) and confirm success.
- [ ] Verify the service is healthy by checking the readiness and liveness probes (`kubectl rollout status deployment/feedback-service`).
- [ ] Notify the operations and support teams that the feedback service is now live in production.

## Next Steps:

- Complete all checklist items
- Monitor after release
