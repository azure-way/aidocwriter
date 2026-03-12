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

variable "api_images" {
  type = map(object({
    image        = string
    min_replicas = optional(number, 1)
    max_replicas = optional(number, 1)
  }))
}

variable "worker_job_image" {
  type = string
}

variable "worker_jobs" {
  type = map(object({
    stage                    = string
    kind                     = string
    queue                    = optional(string)
    topic                    = optional(string)
    subscription             = optional(string)
    custom_rule_type         = string
    scale_metadata           = map(string)
    polling_interval_seconds = optional(number, 30)
    min_executions           = optional(number, 0)
    max_executions           = optional(number, 10)
    parallelism              = optional(number, 1)
    replica_completion_count = optional(number, 1)
    replica_retry_limit      = optional(number, 3)
    replica_timeout_seconds  = optional(number, 1800)
  }))
  default = {}
}

variable "api_env" {
  type    = map(string)
  default = {}
}

variable "api_ports" {
  type    = map(number)
  default = {}

}

variable "ui_images" {
  description = "Map of UI container images"
  type = map(object({
    image        = string
    min_replicas = optional(number, 1)
    max_replicas = optional(number, 1)
  }))
  default = {}
}

variable "ui_ports" {
  description = "Map of UI container ports"
  type        = map(number)
  default     = {}
}

variable "ui_env" {
  type    = map(string)
  default = {}
}

variable "ui_secrets" {
  description = "Secrets for the UI container app"
  type = list(object({
    name                = string
    env_name            = string
    key_vault_secret_id = string
    identity            = string
  }))
  default = []
}

variable "worker_env" {
  type    = map(string)
  default = {}
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "managed_identity_id" {
  type        = string
  description = "The ID of the managed identity to use for the container apps"
}

variable "api_secrets" {
  description = "Secrets for the API container app"

  type = list(object({
    name                = string
    env_name            = string
    key_vault_secret_id = string
    identity            = string
  }))
  default = []
}


variable "plantuml_server_name" {
  type    = string
  default = "aidocwriter-plantuml"
}
