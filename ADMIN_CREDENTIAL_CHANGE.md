# Admin credential change

New intended admin login:

- Username: `gvpowers@admin`
- Password: `admin@gvpowerssalem`

The application defaults have been updated.

If you are deploying over an EXISTING PostgreSQL database, run the one-time migration after activating the ERP virtualenv:

```bash
export ADMIN_USERNAME='gvpowers@admin'
export ADMIN_PASSWORD='admin@gvpowerssalem'
python scripts/set_admin_credentials.py
```

Do not commit a production `.env` containing the password to Git. After the migration, store the credentials in your server's protected environment configuration as appropriate.

The migration refuses to overwrite a non-admin account using the target username.
