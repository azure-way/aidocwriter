variable "name_prefix" {
  type = string
}

variable "location" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "log_analytics_id" {
  type = string
}

variable "container_registry_login" {
  type = string
}

variable "api_image" {
  type = string
}

variable "functions_images" {
  type = map(string)
}

variable "api_env" {
  type    = map(string)
  default = {}
}

variable "functions_env" {
  type    = map(string)
  default = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "managed_identity_id" {
  type = string
  description = "The ID of the managed identity to use for the container apps"
}

variable "api_secrets" {
  description = "Secrets for the API container app"

  type = list(object({
    name                  = string
    env_name              = string
    key_vault_secret_id   = string
    identity              = string
  }))
  default = []
}
