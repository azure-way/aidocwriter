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

resource "azurerm_key_vault_secret" "secret_1" {
  name         = "storage-connection-string"
  value        = azurerm_storage_account.main.primary_connection_string
  key_vault_id = var.key_vault_id
}

output "account_name" {
  value = azurerm_storage_account.main.name
}

output "connection_string_kv_id" {
  value = azurerm_key_vault_secret.secret_1.versionless_id
  
}

output "connection_string_id" {
  value = azurerm_key_vault_secret.secret_1.id
  
}