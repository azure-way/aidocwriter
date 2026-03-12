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
    min_replicas = try(each.value.min_replicas, 1)
    max_replicas = try(each.value.max_replicas, 1)

    container {
      name   = each.key
      image  = each.value.image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "PLANTUML_SERVER_URL"
        value = "https://aidocwriter-plantuml.${azurerm_container_app_environment.main.default_domain}"
      }

      env {
        name  = "AZURE_CLIENT_ID"
        value = var.managed_identity_client_id
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
      allowed_origins    = ["http://localhost:3000", "https://aidocwriter-ui.${azurerm_container_app_environment.main.default_domain}", "https://docwriter-studio.azureway.cloud"]
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

resource "azurerm_container_app" "ui" {
  for_each = var.ui_images

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
    min_replicas = try(each.value.min_replicas, 1)
    max_replicas = try(each.value.max_replicas, 1)

    container {
      name   = each.key
      image  = each.value.image
      cpu    = 0.25
      memory = "0.5Gi"




      dynamic "env" {
        for_each = var.ui_env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.ui_secrets
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
    target_port                = var.ui_ports[each.key]

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }

    # cors {
    #   allowed_origins    = ["http://localhost:3000", "https://docwriter-studio.azureway.cloud"]
    #   allowed_methods    = ["GET", "POST", "OPTIONS"]
    #   allowed_headers    = ["*"]
    #   max_age_in_seconds = 86400
    # }
  }

  dynamic "secret" {
    for_each = var.ui_secrets
    content {
      name                = secret.value.name
      key_vault_secret_id = secret.value.key_vault_secret_id
      identity            = secret.value.identity
    }
  }
}


resource "azurerm_container_app_job" "workers" {
  for_each = var.worker_jobs

  name                         = "${var.name_prefix}-${each.key}"
  location                     = var.location
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.main.id
  workload_profile_name        = "Consumption"
  replica_timeout_in_seconds   = try(each.value.replica_timeout_seconds, 1800)
  replica_retry_limit          = try(each.value.replica_retry_limit, 3)
  tags                         = var.tags

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

  event_trigger_config {
    parallelism              = try(each.value.parallelism, 1)
    replica_completion_count = try(each.value.replica_completion_count, 1)

    scale {
      min_executions              = try(each.value.min_executions, 0)
      max_executions              = try(each.value.max_executions, 10)
      polling_interval_in_seconds = try(each.value.polling_interval_seconds, 30)

      rules {
        name             = "service-bus"
        custom_rule_type = each.value.custom_rule_type
        metadata         = each.value.scale_metadata
      }
    }
  }

  template {
    container {
      name   = "worker"
      image  = var.worker_job_image
      cpu    = 0.25
      memory = "0.5Gi"

      command = ["python", "-m", "docwriter.job_runner"]

      env {
        name  = "PLANTUML_SERVER_URL"
        value = "https://${var.plantuml_server_name}.${azurerm_container_app_environment.main.default_domain}"
      }

      env {
        name  = "AZURE_CLIENT_ID"
        value = var.managed_identity_client_id
      }

      env {
        name  = "DOCWRITER_WORKER_STAGE"
        value = each.value.stage
      }

      env {
        name  = "DOCWRITER_WORKER_KIND"
        value = each.value.kind
      }

      env {
        name  = "DOCWRITER_WORKER_QUEUE"
        value = try(each.value.queue, "")
      }

      env {
        name  = "DOCWRITER_WORKER_TOPIC"
        value = try(each.value.topic, "")
      }

      env {
        name  = "DOCWRITER_WORKER_SUBSCRIPTION"
        value = try(each.value.subscription, "")
      }

      env {
        name  = "DOCWRITER_MAX_MESSAGES_PER_EXECUTION"
        value = "1"
      }

      dynamic "env" {
        for_each = var.worker_env
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
