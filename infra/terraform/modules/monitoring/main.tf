resource "azurerm_log_analytics_workspace" "main" {
  name                = "${var.name_prefix}-law"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_application_insights" "main" {
  name                = "${var.name_prefix}-ai"
  location            = var.location
  resource_group_name = var.resource_group_name
  application_type    = "web"
  workspace_id        = azurerm_log_analytics_workspace.main.id
  tags                = var.tags
}

resource "azurerm_key_vault_secret" "secret_1" {
  name         = "app-insights-instrumentation-key"
  value        = azurerm_application_insights.main.instrumentation_key
  key_vault_id = var.key_vault_id
}


output "log_analytics_id" {
  value = azurerm_log_analytics_workspace.main.id
}

output "app_insights_kv_id" {
  value = azurerm_key_vault_secret.secret_1.versionless_id

}

output "app_insights_secret_id" {
  value = azurerm_key_vault_secret.secret_1.resource_versionless_id

}