> Previously, we looked at [Values (Helm)](09_values-helm.md).

# Chapter 10: Architecture Diagrams
## Class Diagram
Key classes and their relationships in **20250707_1820_code-kubernetes-cfg-sample-project**.
```mermaid
classDiagram
    class Chart {
        +apiVersion: str
        +kind: str
        +metadata: dict
        +spec: dict
    }
    class Values {
        +replicaCount: int
        +image: dict
        +service: dict
    }
    class Deployment {
        +apiVersion: str
        +kind: str
        +metadata: dict
        +spec: dict
    }
    class Service {
        +apiVersion: str
        +kind: str
        +metadata: dict
        +spec: dict
    }
    class Kustomization {
      +apiVersion: str
      +kind: str
      +resources: list
      +patches: list
    }
    Deployment "1" -- "1" Service : Exposes
    Chart "1" *-- "1..*" Deployment : Manages
    Chart "1" *-- "1..*" Service : Manages
    Chart "1" *-- "1" Values : Configured By
    Kustomization "1" *-- "1..*" Deployment : Manages
    Kustomization "1" *-- "1..*" Service : Manages
```
## Package Dependencies
High-level module and package structure of **20250707_1820_code-kubernetes-cfg-sample-project**.
```mermaid
graph TD
    A["README.md"]
    B["guestbook-chart/Chart.yaml"]
    C["guestbook-chart/values.yaml"]
    D["guestbook-chart/values.staging.yaml"]
    E["frontend-deployment.yaml"]
    F["frontend-service.yaml"]
    G["redis-leader-deployment.yaml"]
    H["redis-leader-service.yaml"]
    I["_helpers.tpl"]
    J["kustomize/base/kustomization.yaml"]
    K["production/kustomization.yaml"]
    L["production/frontend-patch.yaml"]
    B -->|"uses"| E
    B -->|"uses"| F
    B -->|"uses"| G
    B -->|"uses"| H
    B -->|"uses"| I
    E -->|"uses"| I
    F -->|"uses"| I
    G -->|"uses"| I
    H -->|"uses"| I
    J -->|"bases"| K
    K --> L
    K -->|"uses"| J
    B --> C
    B --> D
```
## Sequence Diagrams
These diagrams illustrate various interaction scenarios, showcasing operations between components for specific use cases.
### Deploying a new application using a Helm Chart with customized Values.
```mermaid
sequenceDiagram
    participant User
    participant CLI
    participant KubernetesAPI
    participant Helm
    participant KubernetesCluster
    User->>CLI: Deploy application using Helm Chart with custom values
    activate CLI
    CLI->>Helm: helm install <release_name> <chart_location> --values <values_file>
    activate Helm
    Helm->>KubernetesAPI: Create/Update resources in Kubernetes cluster
    activate KubernetesAPI
    KubernetesAPI->>KubernetesCluster: Apply resource definitions
    activate KubernetesCluster
    alt Success
        KubernetesCluster-->>KubernetesAPI: Resources applied successfully
        KubernetesAPI-->>Helm: Deployment successful
        Helm-->>CLI: Application deployed successfully
        CLI-->>User: Application deployed successfully
    else Failure
        KubernetesCluster-->>KubernetesAPI: Resources application failed
        KubernetesAPI-->>Helm: Deployment failed
        Helm-->>CLI: Application deployment failed
        CLI-->>User: Application deployment failed
    end
    deactivate KubernetesCluster
    deactivate KubernetesAPI
    deactivate Helm
    deactivate CLI
```
### Scaling a Deployment by updating the replica count.
```mermaid
sequenceDiagram
    participant User
    participant kubectl
    participant API_Server
    participant Deployment
    participant ReplicaSet
    participant Pod
    User->>kubectl: kubectl edit deployment
    activate kubectl
    kubectl->>API_Server: Update deployment spec (replica count)
    activate API_Server
    API_Server->>Deployment: Update deployment
    Deployment->>ReplicaSet: Create/Update ReplicaSet
    ReplicaSet->>Pod: Create/Delete Pods
    Pod-->>ReplicaSet: Pod Status updates
    ReplicaSet-->>Deployment: Replicas status
    Deployment-->>API_Server: Deployment status
    API_Server-->>kubectl: Update applied
    kubectl-->>User: Success message
    deactivate API_Server
    deactivate kubectl
```
### Exposing an application running in a Pod through a Service.
```mermaid
sequenceDiagram
    participant User
    participant kubectl
    participant API
    participant KubeProxy
    participant Pod
    User->>kubectl: Create Service YAML
    kubectl->>API: Apply Service configuration
    activate API
    API->>API: Create Service object
    API-->>kubectl: Service created
    deactivate API
    kubectl->>User: Service created confirmation
    User->>User: Access Service IP:Port
    User->>KubeProxy: Request to Service IP:Port
    activate KubeProxy
    KubeProxy->>KubeProxy: Route to Pod
    KubeProxy->>Pod: Forward request
    activate Pod
    Pod->>Pod: Process request
    Pod-->>KubeProxy: Response
    deactivate Pod
    KubeProxy-->>User: Response
    deactivate KubeProxy
```
### Updating a Container Image in a Deployment via Kustomize.
```mermaid
sequenceDiagram
    participant User
    participant Kustomize
    participant KubernetesAPI
    participant KubernetesWorkerNode
    User->>Kustomize: Update image tag in Kustomization file
    activate Kustomize
    Kustomize->>Kustomize: Generate updated Kubernetes manifests
    Kustomize-->>User: Updated manifests
    deactivate Kustomize
    User->>KubernetesAPI: Apply updated manifests
    activate KubernetesAPI
    KubernetesAPI->>KubernetesAPI: Validate manifests
    KubernetesAPI->>KubernetesAPI: Update Deployment configuration
    KubernetesAPI-->>User: Deployment updated
    deactivate KubernetesAPI
    KubernetesAPI->>KubernetesWorkerNode: Request updated container image
    activate KubernetesWorkerNode
    KubernetesWorkerNode->>KubernetesWorkerNode: Pull new image
    KubernetesWorkerNode->>KubernetesWorkerNode: Terminate old container
    KubernetesWorkerNode->>KubernetesWorkerNode: Start new container
    KubernetesWorkerNode-->>KubernetesAPI: Container updated
    deactivate KubernetesWorkerNode
```
### Rolling back a Deployment to a previous version after a failed update.
```mermaid
sequenceDiagram
    participant User
    participant kubectl
    participant API_Server
    participant Deployment
    participant ReplicaSet
    User->>kubectl: kubectl rollout undo deployment <deployment_name>
    activate kubectl
    kubectl->>API_Server: Request to rollback Deployment
    activate API_Server
    API_Server->>Deployment: Get current Deployment details
    Deployment-->>API_Server: Current Deployment details
    API_Server->>ReplicaSet: Get previous ReplicaSet version
    ReplicaSet-->>API_Server: Previous ReplicaSet version details
    API_Server->>Deployment: Update Deployment to previous version
    Deployment-->>API_Server: Deployment updated
    API_Server-->>kubectl: Rollback initiated
    kubectl-->>User: Rollback initiated
    deactivate API_Server
    deactivate kubectl
```

> Next, we will examine [Code Inventory](11_code_inventory.md).


---

*Generated by [SourceLens AI](https://github.com/openXFlow/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `Python`*