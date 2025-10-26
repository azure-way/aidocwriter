resource "azurerm_container_app_environment" "main" {
  name                       = "${var.name_prefix}-cae"
  location                   = var.location
  resource_group_name        = var.resource_group_name
  log_analytics_workspace_id = var.log_analytics_id
  tags                       = var.tags

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
    maximum_count         = 0
    minimum_count         = 0
  }
}

resource "azurerm_container_app" "api" {
  for_each = var.api_images

  name                         = "${var.name_prefix}-${each.key}"
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "SystemAssigned, UserAssigned"
    identity_ids = [var.managed_identity_id]
  }

  registry {
    server   = var.container_registry_login
    identity = var.managed_identity_id
  }

  template {
    container {
      name   = each.key
      image  = each.value
      cpu    = 0.5
      memory = "1Gi"

      env { 
        name = "CONTAINER_APP_ENVIRONMENT_DOMAIN"
        value = azurerm_container_app_environment.main.default_domain
      }

      dynamic "env" {
        for_each = var.api_env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.api_secrets
        content {
          name        = env.value.env_name
          secret_name = env.value.name
        }
      }
    }
  }

  ingress {
    allow_insecure_connections = false
    external_enabled           = true
    target_port                = var.api_ports[each.key]

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }

    cors {
      allowed_origins    = ["http://localhost:3000"]
      allowed_methods    = ["GET", "POST", "OPTIONS"]
      allowed_headers    = ["*"]
      max_age_in_seconds = 86400
    }
  }

  dynamic "secret" {
    for_each = var.api_secrets
    content {
      name                = secret.value.name
      key_vault_secret_id = secret.value.key_vault_secret_id
      identity            = secret.value.identity
    }
  }
}

resource "azurerm_container_app" "functions" {
  for_each = var.functions_images

  name                         = each.key
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.main.id
  revision_mode                = "Single"
  tags                         = var.tags

  workload_profile_name        = "Consumption"
  
  identity {
    type         = "SystemAssigned, UserAssigned"
    identity_ids = [var.managed_identity_id]
  }

  registry {
    server   = var.container_registry_login
    identity = var.managed_identity_id
  }

  dynamic "secret" {
    for_each = var.api_secrets
    content {
      name                = secret.value.name
      key_vault_secret_id = secret.value.key_vault_secret_id
      identity            = secret.value.identity
    }
  }

  template {
    container {
      name   = "functions"
      image  = each.value
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "WEBSITE_RUN_FROM_PACKAGE"
        value = "0"
      }

      env { 
        name = "CONTAINER_APP_ENVIRONMENT_DOMAIN"
        value = azurerm_container_app_environment.main.default_domain
      }

      dynamic "env" {
        for_each = var.functions_env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.api_secrets
        content {
          name        = env.value.env_name
          secret_name = env.value.name
        }
      }
    }
  }
}

output "container_apps_environment_name" {
  value = azurerm_container_app_environment.main.name
}

output "api_urls" {
  value = [for api in azurerm_container_app.api : api.ingress[0].fqdn]
}
