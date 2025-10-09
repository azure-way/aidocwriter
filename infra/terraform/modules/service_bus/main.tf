resource "azurerm_servicebus_namespace" "main" {
  name                = "${var.name_prefix}-bus"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "Standard"
  tags                = var.tags
}

resource "azurerm_servicebus_topic" "status" {
  name                 = "${var.name_prefix}-status"
  namespace_id         = azurerm_servicebus_namespace.main.id
  partitioning_enabled = true
}

resource "azurerm_servicebus_subscription" "console" {
  name                = "console"
  topic_id            = azurerm_servicebus_topic.status.id
  max_delivery_count  = 10
}

resource "azurerm_servicebus_queue" "queues" {
  for_each                     = toset(var.queues)

  name                         = each.value
  namespace_id                 = azurerm_servicebus_namespace.main.id

  max_delivery_count           = 10
  lock_duration                = "PT5M"
  default_message_ttl          = "P14D"
  
  dead_lettering_on_message_expiration = true
}

output "namespace_name" {
  value = azurerm_servicebus_namespace.main.name
}

output "topic_name" {
  value = azurerm_servicebus_topic.status.name
}

output "primary_connection_string" {
  value       = azurerm_servicebus_namespace.main.default_primary_connection_string
  sensitive   = true
}
