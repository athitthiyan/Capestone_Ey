# Wraps the official EventStoreDB image to run as root so it can write to
# Railway's volume-mounted /var/lib/eventstore, which is owned by root by
# default. The stock image drops to a non-root "eventstore" user, which
# causes "Permission denied" on the bind-mounted volume.
FROM eventstore/eventstore:23.10.0-bookworm-slim
USER root
