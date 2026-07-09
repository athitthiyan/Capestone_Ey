-- Local PostgreSQL setup for GL Guardian.
-- Use pgAdmin Query Tool while connected to the default "postgres" database.

-- Step 1: create or update the local login role.
DO
$$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles WHERE rolname = 'gl_guardian'
   ) THEN
      CREATE ROLE gl_guardian LOGIN PASSWORD 'gl_guardian_dev_password';
   ELSE
      ALTER ROLE gl_guardian WITH LOGIN PASSWORD 'gl_guardian_dev_password';
   END IF;
END
$$;

-- Step 2: run this statement separately if "gl_guardian" is not already
-- listed under Databases in pgAdmin. CREATE DATABASE cannot be run inside
-- another transaction block.
CREATE DATABASE gl_guardian OWNER gl_guardian;

-- Step 3: after creating the database, right-click "gl_guardian" in pgAdmin,
-- open Query Tool for that database, and run these grants.
GRANT ALL PRIVILEGES ON DATABASE gl_guardian TO gl_guardian;
GRANT ALL ON SCHEMA public TO gl_guardian;
