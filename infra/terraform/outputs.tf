output "log_analytics_workspace_id" {
  value = module.monitoring.log_analytics_id
}

output "storage_account_name" {
  value = module.storage.account_name
}

output "service_bus_topic_name" {
  value = module.service_bus.topic_name
}

output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "service_bus_namespace_name" {
  value = module.service_bus.namespace_name
}

output "service_bus_connection_string" {
  value       = module.service_bus.primary_connection_string
  description = "Primary connection string for Azure Service Bus namespace"
  sensitive   = true
}

output "storage_account_connection_string" {
  value       = module.storage.connection_string
  sensitive   = true
}