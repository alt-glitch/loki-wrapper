
# Loki Semantic Layer

## Installation Steps

1. **Clone the Repository**

   First, clone this repository to your local system. This contains all required configuration files.

2. **Start Grafana Loki**
   ```bash
   cd run_loki
   docker-compose up -d
   ```
3. **Access the Services**
   - **Grafana**: Open your browser and go to `http://localhost:3000/`. Grafana is already configured with Loki as a datasource, and you can start creating dashboards to visualize logs.
## Architectural Overview
Everything is stored in the `.data` directory locally. MinIO is used for storage.

- **Loki**: Central log aggregation system, using MinIO for storage.
- **MinIO**: Object storage for logs, mimicking S3 storage locally.
- **Grafana**: Visualization tool for querying and visualizing logs stored in Loki.
- **Nginx Gateway**: Routes queries to the appropriate Loki components (`read`, `write`, etc.).

## Extensions and Utilities

In addition to the core functionality provided by the logging system, `logcli` is a command-line tool that interacts directly with Loki, providing a way to query and tail logs without the need for a web interface like Grafana. `logcli` offers powerful capabilities for developers and operators who prefer working within terminal environments or require scriptable access to log data.

### Installing `logcli`

`logcli` is part of the Grafana Loki project, and its installation is straightforward:

1. Visit the [Loki releases page](https://github.com/grafana/loki/releases) on GitHub.
2. Select the appropriate version of `logcli` for your operating system and architecture.
3. Download the binary and make it executable.

For example, on a Unix-like system, you might use:

```bash
curl -O -L "https://github.com/grafana/loki/releases/download/v3.0.0/logcli-linux-amd64.zip"
unzip logcli-linux-amd64.zip
chmod +x logcli-linux-amd64
mv logcli-linux-amd64 /usr/local/bin/logcli
```

### Running `logcli`

To run `logcli`, you need the address of your Loki server and optionally an OrgID if you are using multi-tenancy. The basic syntax for querying logs with `logcli` is:

```bash
logcli --addr=http://localhost:3100 query "{container=\"run_loki-flog-1\"}"
```

Replace `http://localhost:3100` with the appropriate Loki server address in your setup.

### Warning: OrgID Required for Multi-Tenant Setups

⚠️ **IMPORTANT**: When using a multi-tenant Loki setup, failing to specify the correct OrgID for queries (including with `logcli`) will result in no data being returned or an authorization error. This is a critical step that must not be overlooked.

Depending on your Loki configuration and infrastructure (such as the provided Nginx gateway), you may need to include an HTTP header (`X-Scope-OrgID`) in your requests. For `logcli`, use the `--org-id` flag:

```bash
logcli --addr=http://localhost:3100 --org-id=tenant1 query "{container=\"run_loki-flog-1\"}"
```

Ensure you adjust the `--org-id` value according to your specific tenant configuration. Failure to do so may lead to unexpected behavior or data access issues.
