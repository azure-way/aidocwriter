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
  description = "Optional Log Analytics workspace id for diagnostic settings"
  type        = string
  default     = ""
}

variable "container_name" {
  type    = string
  default = "docwriter"
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "key_vault_id" {
  type = string

}
