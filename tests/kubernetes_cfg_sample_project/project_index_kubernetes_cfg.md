# Kubernetes Guestbook Application Deployment

This document provides an overview of the `kubernetes_cfg_sample_project`, including its file structure and links to individual file analyses. This project contains Kubernetes manifests to deploy a multi-tier guestbook application using both Helm and Kustomize.

## Project Structure

The project is organized into `guestbook-chart` for Helm-based deployment and `kustomize` for managing environment-specific overlays. This structure demonstrates two common, powerful patterns for managing Kubernetes configurations.

```bash
kubernetes_cfg_sample_project/
├── README.md
├── guestbook-chart/
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values.staging.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── frontend-deployment.yaml
│       ├── frontend-service.yaml
│       ├── redis-leader-deployment.yaml
│       ├── redis-leader-service.yaml
│       ├── redis-follower-deployment.yaml
│       └── redis-follower-service.yaml
└── kustomize/
    ├── base/
    │   └── kustomization.yaml
    └── overlays/
        └── production/
            ├── kustomization.yaml
            └── frontend-patch.yaml
```

## File Index and Descriptions

Below is a list of all key files within the project. Each link leads to a detailed breakdown of the file's purpose and content.

*   **[README.md](./README.md)**: Describes the application architecture and the different deployment strategies (Helm vs. Kustomize).

### `guestbook-chart/` Directory - Helm Chart

*   **[guestbook-chart/Chart.yaml](./guestbook-chart/Chart.yaml)**: The main metadata file for the Helm chart, defining its name, version, and description.
*   **[guestbook-chart/values.yaml](./guestbook-chart/values.yaml)**: Contains the default configuration values for the Helm chart, such as replica counts and image names.
*   **[guestbook-chart/values.staging.yaml](./guestbook-chart/values.staging.yaml)**: An example of an environment-specific values file for overriding defaults in a staging environment.
*   **[guestbook-chart/templates/](./guestbook-chart/templates/)**: This directory contains the Kubernetes manifest templates.
    *   **[.../_helpers.tpl](./guestbook-chart/templates/_helpers.tpl)**: Defines common Helm template helpers, like standard labels.
    *   **[.../frontend-*.yaml](./guestbook-chart/templates/frontend-deployment.yaml)**: Templates for the frontend Deployment and Service.
    *   **[.../redis-leader-*.yaml](./guestbook-chart/templates/redis-leader-deployment.yaml)**: Templates for the Redis leader Deployment and Service.
    *   **[.../redis-follower-*.yaml](./guestbook-chart/templates/redis-follower-deployment.yaml)**: Templates for the Redis follower Deployment and Service.

### `kustomize/` Directory - Kustomize Overlays

*   **[kustomize/base/kustomization.yaml](./kustomize/base/kustomization.yaml)**: The base Kustomize configuration, which in this case uses the Helm chart as its foundation.
*   **[kustomize/overlays/production/kustomization.yaml](./kustomize/overlays/production/kustomization.yaml)**: The Kustomize configuration for the `production` environment, which points to the `base` and applies specific patches.
*   **[kustomize/overlays/production/frontend-patch.yaml](./kustomize/overlays/production/frontend-patch.yaml)**: A patch that modifies the base configuration, specifically to increase the replica count of the frontend for production.

## Project Configuration

The following settings from `config.json` were used for the analysis of this project.

> **Note:** The configuration shown below is a simplified subset specific to this analysis run (e.g., for a command like `sourcelens --language english code --dir tests/kubernetes_cfg_sample_project`). A complete `config.json` file for full application functionality must include all profiles (language and LLM) and configuration blocks for all supported flows (e.g., `FL01_code_analysis`, `FL02_web_crawling`).

```json
{
  "common": {
    "common_output_settings": {
      "default_output_name": "auto-generated",
      "main_output_directory": "output",
      "generated_text_language": "english"
    },
    "logging": {
      "log_dir": "logs",
      "log_level": "INFO"
    },
    "cache_settings": {
      "use_llm_cache": true,
      "llm_cache_file": ".cache/llm_cache.json"
    },
    "llm_default_options": {
      "max_retries": 5,
      "retry_wait_seconds": 20
    }
  },
  "FL01_code_analysis": {
    "enabled": true,
    "active_language_profile_id": "kubernetes_yaml_default",
    "active_llm_provider_id": "gemini_flash_main",
    "diagram_generation": {
      "enabled": true
    },
    "output_options": {
      "include_source_index": true,
      "include_project_review": true
    }
  },
  "profiles": {
    "language_profiles": [
      {
        "profile_id": "kubernetes_yaml_default",
        "language_name_for_llm": "Kubernetes Configurations (YAML)",
        "parser_type": "llm",
        "include_patterns": [
          "*.yaml", "*.yml", "kustomization.yaml", "Chart.yaml", "values.yaml", "README.md"
        ]
      }
    ],
    "llm_profiles": [
      {
        "provider_id": "gemini_flash_main",
        "is_local_llm": false,
        "provider": "gemini",
        "model": "gemini-2.0-flash",
        "api_key_env_var": "GEMINI_API_KEY",
        "api_key": "Your_GEMINI_API_KEY"
      }
    ]
  }
}
```
---

*Generated by [SourceLens AI](https://github.com/openXFlow/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `Kubernetes Configurations (YAML)`*
