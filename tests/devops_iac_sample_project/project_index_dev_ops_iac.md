# DevOps IaC Sample Project

This document provides an overview of the `devops_iac_sample_project`, including its file structure and links to individual file analyses. This project uses a combination of Terraform, Ansible, and Docker to define and deploy a multi-tier web application.

## Project Structure

The project is structured by technology, with dedicated directories for `terraform`, `ansible`, and the application's `app` (Docker) definitions. This separation clearly delineates the different stages of the Infrastructure as Code (IaC) pipeline.

```bash
devops_iac_sample_project/
├── README.md
├── ansible/
│   ├── inventory.ini
│   ├── playbook.yml
│   └── roles/
│       └── docker_app/
│           ├── tasks/
│           │   └── main.yml
│           └── templates/
│               └── docker-compose.yml.j2
├── app/
│   ├── Dockerfile
│   └── docker-compose.yml
└── terraform/
    ├── main.tf
    ├── outputs.tf
    ├── terraform.tfvars
    └── variables.tf
```

## File Index and Descriptions

Below is a list of all key files within the project. Each link leads to a detailed breakdown of the file's purpose and content.

*   **[README.md](./README.md)**: Describes the project architecture and the deployment workflow.

### `terraform/` Directory - Infrastructure Provisioning

*   **[terraform/main.tf](./terraform/main.tf)**: The main Terraform file that defines the cloud resources to be provisioned (VPC, subnets, and virtual machine instances).
*   **[terraform/variables.tf](./terraform/variables.tf)**: Declares input variables for the Terraform configuration, such as the AWS region.
*   **[terraform/outputs.tf](./terraform/outputs.tf)**: Defines the outputs from the Terraform run, such as the public IP addresses of the created servers, which are used by Ansible.
*   **[terraform/terraform.tfvars](./terraform/terraform.tfvars)**: A file for providing values to the input variables (example file).

### `ansible/` Directory - Configuration Management

*   **[ansible/inventory.ini](./ansible/inventory.ini)**: The Ansible inventory file, which lists the servers to be configured. It is intended to be populated dynamically from the Terraform output.
*   **[ansible/playbook.yml](./ansible/playbook.yml)**: The main Ansible playbook that orchestrates the configuration of the target servers, including installing Docker and deploying the application.
*   **[ansible/roles/docker_app/tasks/main.yml](./ansible/roles/docker_app/tasks/main.yml)**: The task list for the `docker_app` role, which handles creating directories, templating the Docker Compose file, and starting the services.
*   **[ansible/roles/docker_app/templates/docker-compose.yml.j2](./ansible/roles/docker_app/templates/docker-compose.yml.j2)**: A Jinja2 template for the Docker Compose file, allowing for dynamic configuration based on which host group (web or app) is being targeted.

### `app/` Directory - Application Containerization

*   **[app/Dockerfile](./app/Dockerfile)**: The build instructions for creating the container image for the Python Flask application.
*   **[app/docker-compose.yml](./app/docker-compose.yml)**: A Docker Compose file intended for local development and testing of the application container.

## Project Configuration

The following settings from `config.json` were used for the analysis of this project.

> **Note:** The configuration shown below is a simplified subset specific to this analysis run (e.g., for a command like `sourcelens --language english code --dir tests/devops_iac_sample_project`). A complete `config.json` file for full application functionality must include all profiles (language and LLM) and configuration blocks for all supported flows (e.g., `FL01_code_analysis`, `FL02_web_crawling`).

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
    "active_language_profile_id": "devops_iac_default",
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
        "profile_id": "devops_iac_default",
        "language_name_for_llm": "DevOps & Infrastructure-as-Code (Terraform, Ansible, Docker)",
        "parser_type": "llm",
        "include_patterns": [
          "*.tf", "*.tfvars", "*.hcl", "*.yaml", "*.yml", "playbook.yml",
          "inventory.ini", "Dockerfile", "docker-compose.yml", "*.sh", "README.md"
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

*Generated by [SourceLens AI](https://github.com/openXFlow/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `DevOps & Infrastructure-as-Code (Terraform, Ansible, Docker)`*
