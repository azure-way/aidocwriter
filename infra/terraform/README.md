# Terraform Deployment

This folder contains Terraform configuration for the DocWriter deployment. The root module (`main.tf`) provisions:

- Resource group
- Monitoring stack (Log Analytics + Application Insights)
- Azure Storage account + private container for document artifacts
- Service Bus namespace with queues and status topic
- Container Apps environment hosting the DocWriter API and Functions images

## Structure

```
terraform/
  main.tf             # root composition
  variables.tf
  outputs.tf
  app/                # container app environment + workloads
  monitoring/         # log analytics + app insights
  service_bus/        # namespace, queues, topic/subscription
  storage/            # storage account & container
```

## Usage

1. Export/login to Azure (`az login`).
2. Populate the required variables (images, registry credentials). You can create a `terraform.tfvars` file, e.g.:

```hcl
container_registry_login = "myregistry.azurecr.io"
container_registry_pwd   = "<registry password>"
api_image                = "myregistry.azurecr.io/docwriter-api:latest"
functions_image          = "myregistry.azurecr.io/docwriter-functions:latest"
```

3. (Optional) Configure a remote backend by editing the commented `backend "azurerm"` block in `main.tf`.
4. Initialize and apply:

```bash
terraform init
terraform plan
terraform apply
```

The outputs include connection strings for Service Bus and Storage, container app names, and the public API FQDN. Inject these values as environment variables for the API/functions containers.

> **Note:** The Container Apps definitions expect container images that already contain the FastAPI service and Functions worker. Build & push these images before running Terraform.
