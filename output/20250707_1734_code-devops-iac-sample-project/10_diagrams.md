> Previously, we looked at [Virtual Private Cloud (VPC)](09_virtual-private-cloud-vpc.md).

# Chapter 10: Architecture Diagrams
## Class Diagram
Key classes and their relationships in **20250707_1734_code-devops-iac-sample-project**.
```mermaid
classDiagram
    class AnsiblePlaybook {
        -inventory_file: str
        +execute() : void
    }
    class AnsibleRole {
        -name: str
        +apply() : void
    }
    class DockerComposeTemplate {
        -template_path: str
        +render(variables: dict) : str
    }
    class TerraformConfig {
        -config_files: list
        +apply() : void
        +output(key: str) : str
    }
    AnsiblePlaybook *-- AnsibleRole : Contains
    AnsibleRole ..> DockerComposeTemplate : Uses
    TerraformConfig o-- TerraformVariables : Reads
    TerraformConfig ..> TerraformOutputs : Creates
    class TerraformVariables{
        +variable_data: dict
    }
    class TerraformOutputs{
        +output_data: dict
    }
```
## Package Dependencies
High-level module and package structure of **20250707_1734_code-devops-iac-sample-project**.
```mermaid
graph TD
    A[README.md]
    B["ansible/inventory.ini"]
    C["ansible/playbook.yml"]
    D["ansible/roles/docker_app/tasks/main.yml"]
    E["ansible/roles/docker_app/templates/docker-compose.yml.j2"]
    F["app/docker-compose.yml"]
    G["app/Dockerfile"]
    H["terraform/main.tf"]
    I["terraform/outputs.tf"]
    J["terraform/terraform.tfvars"]
    K["terraform/variables.tf"]
    C --> B
    C --> D
    D --> E
    H --> I
    H --> J
    H --> K
    D --> F
    D --> G
```
## Sequence Diagrams
These diagrams illustrate various interaction scenarios, showcasing operations between components for specific use cases.
### A developer uses Terraform to provision a VPC in AWS.
```mermaid
sequenceDiagram
    participant User
    participant Terraform
    participant AWS
    User->>Terraform: terraform apply
    activate Terraform
    Terraform->>AWS: Authenticate (AWS Credentials)
    activate AWS
    AWS-->>Terraform: Authentication Successful
    deactivate AWS
    Terraform->>AWS: Create VPC
    activate AWS
    AWS-->>Terraform: VPC Created (VPC ID)
    deactivate AWS
    Terraform->>AWS: Create Subnets
    activate AWS
    AWS-->>Terraform: Subnets Created (Subnet IDs)
    deactivate AWS
    Terraform->>AWS: Create Internet Gateway
    activate AWS
    AWS-->>Terraform: Internet Gateway Created (IGW ID)
    deactivate AWS
    Terraform->>AWS: Create Route Table
    activate AWS
    AWS-->>Terraform: Route Table Created (Route Table ID)
    deactivate AWS
    Terraform->>AWS: Associate Subnets to Route Table
    activate AWS
    AWS-->>Terraform: Subnets Associated
    deactivate AWS
    Terraform-->>User: Infrastructure Created
    deactivate Terraform
```
### Ansible configures a server within the provisioned VPC.
```mermaid
sequenceDiagram
    participant User
    participant Ansible
    participant Server
    participant VPC
    User->>Ansible: Trigger Ansible Playbook
    activate Ansible
    Ansible->>VPC: Check VPC Status
    activate VPC
    VPC-->>Ansible: VPC Ready
    deactivate VPC
    Ansible->>Server: Configure Server
    activate Server
    Server-->>Ansible: Configuration Applied
    deactivate Server
    Ansible-->>User: Configuration Complete
    deactivate Ansible
```
### Docker containers are deployed to the configured server using Docker Compose.
```mermaid
sequenceDiagram
    participant User
    participant DockerCompose
    participant Server
    User->>DockerCompose: Deploy containers
    activate DockerCompose
    DockerCompose->>Server: Deploy Docker Compose configuration
    activate Server
    Server->>Server: Create and start containers
    Server-->>DockerCompose: Deployment status
    DockerCompose-->>User: Deployment complete
    deactivate Server
    deactivate DockerCompose
```
### A user triggers an application deployment via IaC, automating infrastructure updates.
```mermaid
sequenceDiagram
    participant User
    participant IaC_Tool
    participant API
    participant Infrastructure
    User->>IaC_Tool: Trigger Deployment
    activate IaC_Tool
    IaC_Tool->>API: Request Infrastructure Update
    activate API
    API->>Infrastructure: Update Infrastructure
    activate Infrastructure
    alt Success
        Infrastructure-->>API: Infrastructure Updated
        API-->>IaC_Tool: Deployment Successful
    else Failure
        Infrastructure-->>API: Infrastructure Update Failed
        API-->>IaC_Tool: Deployment Failed
    end
    deactivate Infrastructure
    IaC_Tool-->>User: Deployment Status
    deactivate API
    deactivate IaC_Tool
```
### An administrator scales the application by modifying Terraform configuration and applying the changes.
```mermaid
sequenceDiagram
    participant Administrator
    participant Terraform
    participant Infrastructure
    Administrator->>Terraform: Modify Terraform configuration
    Terraform->>Terraform: Plan changes
    Administrator->>Terraform: Apply configuration
    activate Terraform
    Terraform->>Infrastructure: Apply changes to infrastructure
    activate Infrastructure
    Infrastructure-->>Terraform: Infrastructure updated
    deactivate Infrastructure
    Terraform-->>Administrator: Application scaled
    deactivate Terraform
```

> Next, we will examine [Code Inventory](11_code_inventory.md).


---

*Generated by [SourceLens AI](https://github.com/openXFlow/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `Python`*