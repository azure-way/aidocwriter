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

resource "azurerm_key_vault_secret" "auth0_client_secret" {
  name         = "auth0-client-secret"
  value        = var.auth0_client_secret
  key_vault_id = azurerm_key_vault.rbac_example.id
}

resource "azurerm_key_vault_secret" "auth0_secret" {
  name         = "auth0-secret"
  value        = var.auth0_secret
  key_vault_id = azurerm_key_vault.rbac_example.id
}

resource "azurerm_role_assignment" "open_ai_key_secret_reader" {
  scope                = azurerm_key_vault_secret.open_ai_key.resource_versionless_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.ca_identity.principal_id

  depends_on = [module.storage]
}

resource "azurerm_role_assignment" "auth0_client_secret_secret_reader" {
  scope                = azurerm_key_vault_secret.auth0_client_secret.resource_versionless_id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.ca_identity.principal_id

  depends_on = [module.storage]
}

resource "azurerm_role_assignment" "auth0_secret_secret_reader" {
  scope                = azurerm_key_vault_secret.auth0_secret.resource_versionless_id
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
  plantuml_server_name     = var.plantuml_server_name

  tags = var.tags
  api_images = {
    api      = "${module.container_registry.url}/docwriter-api:${var.docker_image_version}"
    plantuml = "${module.container_registry.url}/plantuml-server:${var.docker_image_version}"
  }

  api_ports = {
    api      = 8000
    plantuml = 8080
  }

  ui_images = {
    ui = "${module.container_registry.url}/docwriter-ui:${var.docker_image_version}"
  }

  ui_ports = {
    ui = 3000
  }

  api_env = {
    OPENAI_BASE_URL                  = var.openai_base_url
    OPENAI_API_VERSION               = var.openai_api_version
    SERVICE_BUS_QUEUE_PLAN_INTAKE    = "docwriter-plan-intake"
    SERVICE_BUS_QUEUE_INTAKE_RESUME  = "docwriter-intake-resume"
    SERVICE_BUS_QUEUE_PLAN           = "docwriter-plan"
    SERVICE_BUS_QUEUE_WRITE          = "docwriter-write"
    SERVICE_BUS_QUEUE_REVIEW         = "docwriter-review"
    SERVICE_BUS_QUEUE_REVIEW_GENERAL = "docwriter-review"
    SERVICE_BUS_QUEUE_REVIEW_STYLE   = "docwriter-review-style"
    SERVICE_BUS_QUEUE_REVIEW_COHESION = "docwriter-review-cohesion"
    SERVICE_BUS_QUEUE_REVIEW_SUMMARY = "docwriter-review-summary"
    SERVICE_BUS_QUEUE_VERIFY         = "docwriter-verify"
    SERVICE_BUS_QUEUE_REWRITE        = "docwriter-rewrite"
    SERVICE_BUS_QUEUE_DIAGRAM_PREP   = "docwriter-diagram-prep"
    SERVICE_BUS_QUEUE_DIAGRAM_RENDER = "docwriter-diagram-render"
    SERVICE_BUS_QUEUE_FINALIZE_READY = "docwriter-finalize-ready"
    SERVICE_BUS_TOPIC_STATUS         = module.service_bus.topic_name
    SERVICE_BUS_STATUS_SUBSCRIPTION  = "status-writer"
    AZURE_BLOB_CONTAINER             = "docwriter"
    AUTH0_ISSUER_BASE_URL            = var.auth0_issuer_base_url
    AUTH0_AUDIENCE                   = var.auth0_audience
  }
  functions_images = {
    plan-intake    = "${module.container_registry.url}/docwriter-plan-intake:${var.docker_image_version}"
    intake-resume  = "${module.container_registry.url}/docwriter-intake-resume:${var.docker_image_version}"
    plan           = "${module.container_registry.url}/docwriter-plan:${var.docker_image_version}"
    write          = "${module.container_registry.url}/docwriter-write:${var.docker_image_version}"
    review         = "${module.container_registry.url}/docwriter-review:${var.docker_image_version}"
    verify         = "${module.container_registry.url}/docwriter-verify:${var.docker_image_version}"
    rewrite        = "${module.container_registry.url}/docwriter-rewrite:${var.docker_image_version}"
    finalize       = "${module.container_registry.url}/docwriter-finalize:${var.docker_image_version}"
    status         = "${module.container_registry.url}/docwriter-status:${var.docker_image_version}"
    diagram-render = "${module.container_registry.url}/docwriter-diagram-render:${var.docker_image_version}"
    diagram-prep   = "${module.container_registry.url}/docwriter-diagram-prep:${var.docker_image_version}"
  }
  functions_env = {
    OPENAI_BASE_URL                   = var.openai_base_url
    OPENAI_API_VERSION                = var.openai_api_version
    SERVICE_BUS_QUEUE_PLAN_INTAKE     = "docwriter-plan-intake"
    SERVICE_BUS_QUEUE_INTAKE_RESUME   = "docwriter-intake-resume"
    SERVICE_BUS_QUEUE_PLAN            = "docwriter-plan"
    SERVICE_BUS_QUEUE_WRITE           = "docwriter-write"
    SERVICE_BUS_QUEUE_REVIEW          = "docwriter-review"
    SERVICE_BUS_QUEUE_REVIEW_GENERAL  = "docwriter-review"
    SERVICE_BUS_QUEUE_REVIEW_STYLE    = "docwriter-review-style"
    SERVICE_BUS_QUEUE_REVIEW_COHESION = "docwriter-review-cohesion"
    SERVICE_BUS_QUEUE_REVIEW_SUMMARY  = "docwriter-review-summary"
    SERVICE_BUS_QUEUE_VERIFY          = "docwriter-verify"
    SERVICE_BUS_QUEUE_REWRITE         = "docwriter-rewrite"
    SERVICE_BUS_QUEUE_DIAGRAM_PREP    = "docwriter-diagram-prep"
    SERVICE_BUS_QUEUE_DIAGRAM_RENDER  = "docwriter-diagram-render"
    SERVICE_BUS_QUEUE_FINALIZE_READY  = "docwriter-finalize-ready"
    SERVICE_BUS_TOPIC_STATUS          = module.service_bus.topic_name
    SERVICE_BUS_STATUS_SUBSCRIPTION   = "status-writer"
    AZURE_BLOB_CONTAINER              = "docwriter"
    DOCWRITER_STATUS_TABLE            = "DocWriterStatus"
    DOCWRITER_PLANTUML_REFORMAT_MODEL = "gpt-5.1-codex"
    DOCWRITER_WRITE_BATCH_SIZE        = "4"
    DOCWRITER_DEFAULT_LENGTH_PAGES    = "20"
    DOCWRITER_REVIEW_STYLE_ENABLED    = "False"
    DOCWRITER_REVIEW_COHESION_ENABLED = "False"
    DOCWRITER_REVIEW_SUMMARY_ENABLED  = "False"
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

  ui_env = {
    NEXT_PUBLIC_API_BASE_URL       = "https://aidocwriter-api.gentlecliff-6769fc4f.westeurope.azurecontainerapps.io"
    AUTH0_BASE_URL                 = "https://docwriter-studio.azureway.cloud"
    APP_BASE_URL                   = "https://docwriter-studio.azureway.cloud"
    AUTH0_ISSUER_BASE_URL          = "https://pixelteam.eu.auth0.com"
    AUTH0_DOMAIN                   = "https://pixelteam.eu.auth0.com"
    AUTH0_CLIENT_ID                = "IVMRXTH6H6fJa3022IygQI9DLXVpJkYB"
    AUTH0_AUDIENCE                 = "https://docwriter-api.azureway.cloud"
    AUTH0_SCOPE                    = "openid profile email api offline_access"
    NEXT_PUBLIC_AUTH0_AUDIENCE     = "https://docwriter-api.azureway.cloud"
    NEXT_PUBLIC_AUTH0_SCOPE        = "openid profile email api offline_access"
    NEXT_PUBLIC_PROFILE_ROUTE      = "/auth/profile"
    NEXT_PUBLIC_ACCESS_TOKEN_ROUTE = "/api/auth/access-token"
  }

  ui_secrets = [
    {
      name                = "auth0-client-secret"
      env_name            = "AUTH0_CLIENT_SECRET"
      key_vault_secret_id = azurerm_key_vault_secret.auth0_client_secret.versionless_id
      identity            = azurerm_user_assigned_identity.ca_identity.id
    },
    {
      name                = "auth0-secret"
      env_name            = "AUTH0_SECRET"
      key_vault_secret_id = azurerm_key_vault_secret.auth0_secret.versionless_id
      identity            = azurerm_user_assigned_identity.ca_identity.id
    }
  ]

  depends_on = [time_sleep.wait_60_seconds]
}
