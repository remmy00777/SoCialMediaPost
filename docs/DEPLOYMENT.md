# Deployment

The supported deployment target is a single macOS user account running Docker Desktop. The portal binds to `127.0.0.1`. PostgreSQL and Redis are not published to the host.

`make install` creates a LaunchAgent that calls `scripts/start.sh`. Compose restart policies recover crashed containers. Celery late acknowledgements, idempotency keys, durable database state, and stored workflow records support safe resumption.

The optional Next.js portal can be enabled with:

```bash
docker compose --profile nextjs up -d frontend
```

The default FastAPI-served portal remains available even when the optional Node build is disabled.
