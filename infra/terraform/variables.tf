variable "name_prefix" {
  description = "Prefix used for Azure resource names"
  type        = string
  default     = "aidocwriter"
}

variable "resource_group_name" {
  description = "Name of the resource group"
  type        = string
  default     = "rg-aidocwriter"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "westeurope"
}

variable "plantuml_server_name" {
  type    = string
  default = "aidocwriter-plantuml"
}

variable "tags" {
  description = "Common tags applied to resources"
  type        = map(string)
  default = {
    project = "aidocwriter"
  }
}

variable "service_bus_queues" {
  description = "List of Service Bus queues to create"
  type        = list(string)
  default = [
    "docwriter-plan-intake",
    "docwriter-intake-resume",
    "docwriter-plan",
    "docwriter-write",
    "docwriter-review",
    "docwriter-verify",
    "docwriter-rewrite",
    "docwriter-diagram-prep",
    "docwriter-diagram-render",
    "docwriter-finalize-ready"
  ]
}

variable "openai_base_url" {
  type = string

}

variable "openai_api_version" {
  type = string

}

variable "openai_api_key_secret" {
  type      = string
  sensitive = true

}


variable "auth0_client_secret" {
  type      = string
  sensitive = true
}

variable "auth0_secret" {
  type      = string
  sensitive = true
}

variable "subscription-id" {
  description = "Azure subscription ID"
}

variable "spn-client-id" {
  description = "Client ID of the service principal"
}

variable "spn-client-secret" {
  description = "Secret for service principal"
}

variable "spn-tenant-id" {
  description = "Tenant ID for service principal"
}

variable "docker_image_version" {
  description = "Version tag of the Docker images to deploy"
  type        = string

}
variable "auth0_audience" {
  description = "Auth0 audience for API"
  type        = string
}

variable "auth0_issuer_base_url" {
  description = "Auth0 issuer base URL"
  type        = string
}