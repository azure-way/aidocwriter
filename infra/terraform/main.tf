locals {
  name_prefix = var.name_prefix
}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

module "container_registry" {
  source = "./modules/container_registry"

  resource_group_name = azurerm_resource_group.main.name
  location            = var.location

  name = "${local.name_prefix}acr"
}

resource "azurerm_user_assigned_identity" "ca_identity" {
  location            = var.location
  name                = "ca_identity"
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_role_assignment" "acrpull_mi" {
  scope                = module.container_registry.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.ca_identity.principal_id
}

resource "azurerm_key_vault" "rbac_example" {
  name                        = "${local.name_prefix}-kv"
  location                    = azurerm_resource_group.main.location
  resource_group_name         = azurerm_resource_group.main.name
  enabled_for_disk_encryption = true
  tenant_id                   = data.azurerm_client_config.current.tenant_id
  soft_delete_retention_days  = 7
  purge_protection_enabled    = false

  rbac_authorization_enabled = true
  sku_name                   = "standard"
}

resource "azurerm_role_assignment" "principal_rbac" {
  scope                = azurerm_key_vault.rbac_example.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

resource "azurerm_role_assignment" "service_bus_secret_reader" {
  scope                = module.service_bus.connection_string_secret_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.ca_identity.principal_id

  depends_on = [module.service_bus]
}

resource "azurerm_role_assignment" "storage_secret_reader" {
  scope                = module.storage.connection_string_secret_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.ca_identity.principal_id

  depends_on = [module.storage]
}

resource "azurerm_role_assignment" "app_insights_secret_reader" {
  scope                = module.monitoring.app_insights_secret_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.ca_identity.principal_id

  depends_on = [module.monitoring]
}

resource "azurerm_role_assignment" "app_insights_connection_string_reader" {
  scope                = module.monitoring.app_insights_connection_string_secret_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.ca_identity.principal_id

  depends_on = [module.monitoring]
}


resource "azurerm_key_vault_secret" "open_ai_key" {
  name         = "openai-key"
  value        = var.openai_api_key_secret
  key_vault_id = azurerm_key_vault.rbac_example.id
}

resource "azurerm_role_assignment" "open_ai_key_secret_reader" {
  scope                = azurerm_key_vault_secret.open_ai_key.resource_versionless_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.ca_identity.principal_id

  depends_on = [module.storage]
}

module "monitoring" {
  source              = "./modules/monitoring"
  name_prefix         = local.name_prefix
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
  key_vault_id        = azurerm_key_vault.rbac_example.id
}

module "storage" {
  source              = "./modules/storage"
  name_prefix         = local.name_prefix
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  log_analytics_id    = module.monitoring.log_analytics_id
  tags                = var.tags

  key_vault_id = azurerm_key_vault.rbac_example.id

  depends_on = [azurerm_role_assignment.principal_rbac]
}

module "service_bus" {
  source              = "./modules/service_bus"
  name_prefix         = local.name_prefix
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  queues              = var.service_bus_queues
  tags                = var.tags
  key_vault_id        = azurerm_key_vault.rbac_example.id

  depends_on = [azurerm_role_assignment.principal_rbac]
}

resource "time_sleep" "wait_60_seconds" {
  create_duration = "60s"

  depends_on = [
    azurerm_role_assignment.service_bus_secret_reader,
    azurerm_role_assignment.storage_secret_reader,
    azurerm_role_assignment.open_ai_key_secret_reader,
    azurerm_role_assignment.app_insights_secret_reader,
    azurerm_role_assignment.app_insights_connection_string_reader
  ]
}

module "app" {
  source                   = "./modules/app"
  name_prefix              = local.name_prefix
  location                 = azurerm_resource_group.main.location
  resource_group_name      = azurerm_resource_group.main.name
  log_analytics_id         = module.monitoring.log_analytics_id
  managed_identity_id      = azurerm_user_assigned_identity.ca_identity.id
  container_registry_login = module.container_registry.url
  tags                     = var.tags
  api_images               = {
    api      = "${module.container_registry.url}/docwriter-api:${var.docker_image_version}"
    plantuml = "${module.container_registry.url}/plantuml-server:${var.docker_image_version}"
  }

  api_ports = {
    api      = 80
    plantuml = 8080
  }

  api_env = {
    OPENAI_BASE_URL                 = var.openai_base_url
    OPENAI_API_VERSION              = var.openai_api_version
    SERVICE_BUS_QUEUE_PLAN_INTAKE   = "docwriter-plan-intake"
    SERVICE_BUS_QUEUE_INTAKE_RESUME = "docwriter-intake-resume"
    SERVICE_BUS_QUEUE_PLAN          = "docwriter-plan"
    SERVICE_BUS_QUEUE_WRITE         = "docwriter-write"
    SERVICE_BUS_QUEUE_REVIEW        = "docwriter-review"
    SERVICE_BUS_QUEUE_VERIFY        = "docwriter-verify"
    SERVICE_BUS_QUEUE_REWRITE       = "docwriter-rewrite"
    SERVICE_BUS_QUEUE_FINALIZE      = "docwriter-finalize"
    SERVICE_BUS_TOPIC_STATUS        = module.service_bus.topic_name
    SERVICE_BUS_STATUS_SUBSCRIPTION = "status-writer"
    AZURE_BLOB_CONTAINER            = "docwriter"
    PLANTUML_SERVER_APP_NAME        = "aidocwriter-plantuml"
  }
  functions_images = {
    plan-intake   = "${module.container_registry.url}/docwriter-plan-intake:${var.docker_image_version}"
    intake-resume = "${module.container_registry.url}/docwriter-intake-resume:${var.docker_image_version}"
    plan          = "${module.container_registry.url}/docwriter-plan:${var.docker_image_version}"
    write         = "${module.container_registry.url}/docwriter-write:${var.docker_image_version}"
    review        = "${module.container_registry.url}/docwriter-review:${var.docker_image_version}"
    verify        = "${module.container_registry.url}/docwriter-verify:${var.docker_image_version}"
    rewrite       = "${module.container_registry.url}/docwriter-rewrite:${var.docker_image_version}"
    finalize      = "${module.container_registry.url}/docwriter-finalize:${var.docker_image_version}"
    status        = "${module.container_registry.url}/docwriter-status:${var.docker_image_version}"
  }
  functions_env = {
    OPENAI_BASE_URL                 = var.openai_base_url
    OPENAI_API_VERSION              = var.openai_api_version
    SERVICE_BUS_QUEUE_PLAN_INTAKE   = "docwriter-plan-intake"
    SERVICE_BUS_QUEUE_INTAKE_RESUME = "docwriter-intake-resume"
    SERVICE_BUS_QUEUE_PLAN          = "docwriter-plan"
    SERVICE_BUS_QUEUE_WRITE         = "docwriter-write"
    SERVICE_BUS_QUEUE_REVIEW        = "docwriter-review"
    SERVICE_BUS_QUEUE_VERIFY        = "docwriter-verify"
    SERVICE_BUS_QUEUE_REWRITE       = "docwriter-rewrite"
    SERVICE_BUS_QUEUE_FINALIZE      = "docwriter-finalize"
    SERVICE_BUS_TOPIC_STATUS        = module.service_bus.topic_name
    SERVICE_BUS_STATUS_SUBSCRIPTION = "status-writer"
    AZURE_BLOB_CONTAINER            = "docwriter"
    DOCWRITER_STATUS_TABLE          = "DocWriterStatus"
  }
  api_secrets = [
    {
      name                = "azure-openai-api-key"
      env_name            = "OPENAI_API_KEY"
      key_vault_secret_id = azurerm_key_vault_secret.open_ai_key.versionless_id
      identity            = azurerm_user_assigned_identity.ca_identity.id
    },
    {
      name                = "servicebus-connection-string"
      env_name            = "SERVICE_BUS_CONNECTION_STRING"
      key_vault_secret_id = module.service_bus.connection_string_kv_id
      identity            = azurerm_user_assigned_identity.ca_identity.id
    },
    {
      name                = "storage-connection-string"
      env_name            = "AZURE_STORAGE_CONNECTION_STRING"
      key_vault_secret_id = module.storage.connection_string_kv_id
      identity            = azurerm_user_assigned_identity.ca_identity.id
    },
    {
      name                = "app-insights-instrumentation-key"
      env_name            = "APPINSIGHTS_INSTRUMENTATION_KEY"
      key_vault_secret_id = module.monitoring.app_insights_kv_id
      identity            = azurerm_user_assigned_identity.ca_identity.id
    },
    {
      name                = "app-insights-connection-string"
      env_name            = "APPLICATIONINSIGHTS_CONNECTION_STRING"
      key_vault_secret_id = module.monitoring.app_insights_connection_string_kv_id
      identity            = azurerm_user_assigned_identity.ca_identity.id
    }
  ]

  depends_on = [time_sleep.wait_60_seconds]
}
