## Engineering Notes / Debugging Log

This section documents key implementation and debugging issues encountered during development. The goal is to preserve the reasoning behind important technical decisions and avoid repeating the same debugging process later.

### Frontend Search Flow

I added the search flow through the frontend, including:

- URL query parameter handling
- API request forwarding
- development-only search controls
- search path debugging support

This made it easier to test different search modes from the UI and verify how the request travels from the frontend to the API Gateway and backend services.

### Logger and gRPC Runtime Issue

One issue appeared because the Docker environment was not using the same Protobuf/gRPC runtime assumptions as the locally generated files.

The generated gRPC stub files were produced with Protobuf gencode version 6.31.1, while the Docker images installed runtime version 5.29.6. Because of that mismatch, the service failed during startup validation.

Resolution:

- identified the Protobuf/gRPC version mismatch
- regenerated or aligned the generated `_pb2.py` files with the runtime version used inside Docker
- rebuilt and restarted the Docker stack
- confirmed that the services started correctly after the version alignment

Lesson learned:

Generated files and runtime dependencies must be compatible. A service can work locally and still fail in Docker if the generated code and installed runtime versions are different.

### PostgreSQL Connection Issue

Another issue was related to PostgreSQL connection configuration. The service could not find or connect to the expected database.

Resolution:

- checked the database name and connection URL
- separated environment files per service
- made local configuration independent from Docker configuration
- added clearer environment structure for development

Lesson learned:

Database connection errors are often not code errors. They can come from wrong database names, wrong hostnames, wrong ports, missing environment variables, or mixing local and Docker runtime configuration.

### Mixed Local and Docker Processes

At one point, some services were running locally while others were running in Docker. The API Gateway and Recommendation Service were running, but the Business Service was not running correctly. Because of that, search requests returned no useful results.

The problem was made worse by overlapping ports between local services and Docker containers.

Resolution:

- checked which services were actually running
- verified ports before testing
- avoided mixing local and Docker execution unless intentionally testing that setup
- restarted the correct stack before debugging API behavior

Lesson learned:

Before debugging business logic, first verify the runtime environment: which services are running, on which ports, and whether they are local or containerized.

### gRPC Docker Networking Issue

The gRPC connection behaved differently locally and inside Docker.

Locally, `localhost:50051` works because the service is running on the host machine.

Inside Docker, `localhost` points to the current container, not to another service container. Therefore, a container cannot reach another container through `localhost`.

Resolution:

- used the Docker Compose service name as the gRPC host
- configured the service address through environment variables
- used values such as `business-service:50051` inside Docker instead of `localhost:50051`

Lesson learned:

In Docker, services communicate through Docker network names, not through the host machine's `localhost`.

### Full-Text Search Issue

The search endpoint returned HTTP 500 because the application expected a PostgreSQL full-text search column that did not exist yet in the database.

The code expected:

- `search_vector` column
- FTS trigger
- FTS index
- existing rows to be backfilled

But the database schema was still missing part of that structure.

Resolution:

- added a migration script for the FTS setup
- added the required `search_vector` column
- added trigger logic for keeping the search vector updated
- backfilled existing rows
- added fallback search behavior
- verified that the endpoint no longer fails when FTS is unavailable or incomplete

Lesson learned:

When application code depends on database-generated columns, triggers, indexes, or extensions, the database migration must be applied before the feature can work correctly.

### General Lesson

Many issues were not caused by the main Python code itself, but by the interaction between multiple layers:

- local runtime
- Docker runtime
- environment variables
- service networking
- generated gRPC code
- PostgreSQL schema
- migrations
- frontend request flow
- API Gateway forwarding

This project showed that backend development is not only about writing endpoints. It is also about understanding how services, databases, generated code, configuration, and deployment environments work together.