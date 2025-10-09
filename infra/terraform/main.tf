locals {
  name_prefix = var.name_prefix
}

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

module "monitoring" {
  source              = "./modules/monitoring"
  name_prefix         = local.name_prefix
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

module "storage" {
  source              = "./modules/storage"
  name_prefix         = local.name_prefix
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  log_analytics_id    = module.monitoring.log_analytics_id
  tags                = var.tags
}

module "service_bus" {
  source              = "./modules/service_bus"
  name_prefix         = local.name_prefix
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  queues              = var.service_bus_queues
  tags                = var.tags
}

# module "app" {
#   source                   = "./modules/app"
#   name_prefix              = local.name_prefix
#   location                 = azurerm_resource_group.main.location
#   resource_group_name      = azurerm_resource_group.main.name
#   log_analytics_id         = module.monitoring.log_analytics_id
#   managed_identity_id = azurerm_user_assigned_identity.ca_identity.client_id
#   container_registry_login = module.container_registry.login_server
#   tags                     = var.tags
#   api_image                = "${module.container_registry.login_server}/docwriter-api:v1"
#   api_env = {
#     OPENAI_BASE_URL               = var.openai_base_url
#     OPENAI_API_VERSION            = var.openai_api_version
#     SERVICE_BUS_CONNECTION_STRING = module.service_bus.primary_connection_string
#     SERVICE_BUS_QUEUE_PLAN_INTAKE = "docwriter-plan-intake"
#     SERVICE_BUS_QUEUE_INTAKE_RESUME = "docwriter-intake-resume"
#     SERVICE_BUS_QUEUE_PLAN        = "docwriter-plan"
#     SERVICE_BUS_QUEUE_WRITE       = "docwriter-write"
#     SERVICE_BUS_QUEUE_REVIEW      = "docwriter-review"
#     SERVICE_BUS_QUEUE_VERIFY      = "docwriter-verify"
#     SERVICE_BUS_QUEUE_REWRITE     = "docwriter-rewrite"
#     SERVICE_BUS_QUEUE_FINALIZE    = "docwriter-finalize"
#     SERVICE_BUS_TOPIC_STATUS      = "docwriter-status"
#     AZURE_STORAGE_CONNECTION_STRING = module.storage.connection_string
#     AZURE_BLOB_CONTAINER          = "docwriter"
#   }
#   functions_images = {
#     plan-intake    = "${module.container_registry.login_server}/docwriter-plan-intake:v1"
#     intake-resume  = "${module.container_registry.login_server}/docwriter-intake-resume:v1"
#     plan           = "${module.container_registry.login_server}/docwriter-plan:v1"
#     write          = "${module.container_registry.login_server}/docwriter-write:v1"
#     review         = "${module.container_registry.login_server}/docwriter-review:v1"
#     verify         = "${module.container_registry.login_server}/docwriter-verify:v1"
#     rewrite        = "${module.container_registry.login_server}/docwriter-rewrite:v1"
#     finalize       = "${module.container_registry.login_server}/docwriter-finalize:v1"
#   }
#   functions_env = {
#     OPENAI_BASE_URL               = var.openai_base_url
#     OPENAI_API_VERSION            = var.openai_api_version
#     SERVICE_BUS_CONNECTION_STRING = module.service_bus.primary_connection_string
#     SERVICE_BUS_QUEUE_PLAN_INTAKE = "docwriter-plan-intake"
#     SERVICE_BUS_QUEUE_INTAKE_RESUME = "docwriter-intake-resume"
#     SERVICE_BUS_QUEUE_PLAN        = "docwriter-plan"
#     SERVICE_BUS_QUEUE_WRITE       = "docwriter-write"
#     SERVICE_BUS_QUEUE_REVIEW      = "docwriter-review"
#     SERVICE_BUS_QUEUE_VERIFY      = "docwriter-verify"
#     SERVICE_BUS_QUEUE_REWRITE     = "docwriter-rewrite"
#     SERVICE_BUS_QUEUE_FINALIZE    = "docwriter-finalize"
#     SERVICE_BUS_TOPIC_STATUS      = "docwriter-status"
#     AZURE_STORAGE_CONNECTION_STRING = module.storage.connection_string
#     AZURE_BLOB_CONTAINER          = "docwriter"
#   }
# }
