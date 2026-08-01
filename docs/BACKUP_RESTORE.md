# Backup and Restore

## Backup

`make backup` creates a timestamped archive under `storage/backups`. It includes a PostgreSQL custom-format dump, managed storage archive, environment schema example, and SHA-256 checksums. Secret values from `.env` are not copied into the archive.

## Restore test

Always test restore on a disposable copy or after a second verified backup:

```bash
make restore FILE=storage/backups/socialmediapost-YYYYMMDDTHHMMSSZ.tar.gz
make status
```

The restore script stops API workers, verifies checksums, recreates the database, restores storage, and restarts services.

Encrypt and access-control backup archives before moving them off the Mac.
