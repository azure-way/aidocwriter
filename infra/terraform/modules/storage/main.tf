resource "azurerm_storage_account" "main" {
  name                     = replace(lower("${var.name_prefix}sa"), "-", "")
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  https_traffic_only_enabled = true
  tags                     = var.tags
}

resource "azurerm_storage_container" "documents" {
  name                  = var.container_name
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

output "account_name" {
  value = azurerm_storage_account.main.name
}

output "connection_string" {
  value       = azurerm_storage_account.main.primary_connection_string
  sensitive   = true
}
