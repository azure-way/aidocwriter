# PlantUML Server Container

This folder contains a thin wrapper around the official [plantuml/plantuml-server](https://github.com/plantuml/plantuml-server) image so you can build/push it alongside the other DocWriter containers.

## Features
- Leverages the upstream Jetty-based PlantUML server image.
- Exposes port `8080` (configurable via `PLANTUML_PORT`).
The Container App (or other orchestrator) can configure its own health probe against `/plantuml/png/~h` if needed.

## Build

```bash
docker build -t plantuml-server ./plantuml-server
```

## Run Locally

```bash
docker run -p 8080:8080 plantuml-server
# test rendering
curl --data-binary '@diagram.puml' http://localhost:8080/plantuml/png > diagram.png
```

`diagram.puml` should contain standard PlantUML syntax (e.g. `@startuml` … `@enduml`). The server responds with the rendered PNG (or SVG if you use `/plantuml/svg`).

The upstream image honours `JAVA_OPTS` and other JVM tuning environment variables. Adjust them at deploy time if you need custom memory settings.
