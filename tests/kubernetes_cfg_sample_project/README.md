# Kubernetes Guestbook Application Deployment

This project contains all necessary Kubernetes manifests to deploy a multi-tier guestbook application. The deployment is managed using both Helm and Kustomize to demonstrate different configuration strategies.

## Architecture
The application consists of three main components:
1.  **Frontend**: A PHP-based web application.
2.  **Redis Leader**: A primary Redis instance for write operations.
3.  **Redis Follower**: Replicated Redis instances for read operations to ensure scalability.

## Deployment Strategies
- **Helm (`guestbook-chart/`)**: The entire application is packaged as a Helm chart. This allows for templated, configurable deployments. A `values.staging.yaml` file is provided as an example of environment-specific configuration.
- **Kustomize (`kustomize/`)**: This demonstrates how to manage configuration for different environments (`base` vs. `production`) by applying patches to a common set of resources. The `base` points to the Helm chart, and the `production` overlay applies a patch to increase the replica count.

## How to Deploy
- **Using Helm**: `helm install guestbook ./guestbook-chart -f ./guestbook-chart/values.staging.yaml`
- **Using Kustomize**: `kubectl apply -k kustomize/overlays/production`