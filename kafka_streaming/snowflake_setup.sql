-- =============================================================================
-- Snowflake Setup for Kafka Streaming into ORDERS_INTERACTIVE
-- Run this script in Snowsight as ACCOUNTADMIN
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- =============================================================================
-- Part 1: Create Role for Kafka Connector
-- =============================================================================

CREATE ROLE IF NOT EXISTS KAFKA_CONNECTOR_ROLE;
GRANT ROLE KAFKA_CONNECTOR_ROLE TO ROLE ACCOUNTADMIN;

-- Grant privileges on database and schema
GRANT USAGE ON DATABASE INTERACTIVE_DEMO TO ROLE KAFKA_CONNECTOR_ROLE;
GRANT USAGE ON SCHEMA INTERACTIVE_DEMO.TPCH_INTERACTIVE TO ROLE KAFKA_CONNECTOR_ROLE;

-- Grant INSERT on the existing interactive table (for streaming writes)
GRANT INSERT ON TABLE INTERACTIVE_DEMO.TPCH_INTERACTIVE.ORDERS_INTERACTIVE TO ROLE KAFKA_CONNECTOR_ROLE;
GRANT SELECT ON TABLE INTERACTIVE_DEMO.TPCH_INTERACTIVE.ORDERS_INTERACTIVE TO ROLE KAFKA_CONNECTOR_ROLE;

-- Grants needed by the Kafka connector for Snowpipe Streaming
GRANT CREATE STAGE ON SCHEMA INTERACTIVE_DEMO.TPCH_INTERACTIVE TO ROLE KAFKA_CONNECTOR_ROLE;
GRANT CREATE PIPE ON SCHEMA INTERACTIVE_DEMO.TPCH_INTERACTIVE TO ROLE KAFKA_CONNECTOR_ROLE;

-- =============================================================================
-- Part 2: Create User for Kafka Connector
-- =============================================================================

CREATE USER IF NOT EXISTS KAFKA_USER
  DEFAULT_ROLE = KAFKA_CONNECTOR_ROLE
  DEFAULT_NAMESPACE = INTERACTIVE_DEMO.TPCH_INTERACTIVE;

GRANT ROLE KAFKA_CONNECTOR_ROLE TO USER KAFKA_USER;

-- =============================================================================
-- Part 3: Configure Key Pair Authentication
-- =============================================================================
-- PREREQUISITE: Generate RSA key pair in your terminal:
--
--   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
--   openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
--   cat rsa_key.pub | grep -v "BEGIN\|END" | tr -d '\n'
--
-- Copy the public key output and paste it below (replacing YOUR_PUBLIC_KEY_HERE):

ALTER USER KAFKA_USER SET RSA_PUBLIC_KEY='YOUR_PUBLIC_KEY_HERE';

-- =============================================================================
-- Part 4: Verify Setup
-- =============================================================================

-- Verify user has the public key assigned
DESC USER KAFKA_USER;

-- Verify grants
SHOW GRANTS TO ROLE KAFKA_CONNECTOR_ROLE;

-- Verify table exists and is interactive
SHOW TABLES LIKE 'ORDERS_INTERACTIVE' IN INTERACTIVE_DEMO.TPCH_INTERACTIVE;

-- Check current row count (for baseline before streaming)
SELECT COUNT(*) AS current_row_count
FROM INTERACTIVE_DEMO.TPCH_INTERACTIVE.ORDERS_INTERACTIVE;

-- =============================================================================
-- Part 5: Test KAFKA_USER Connectivity from Terminal
-- =============================================================================
-- After completing Parts 1-4, test that KAFKA_USER can connect using key pair
-- auth from your local terminal. This validates the same auth path the Kafka
-- connector will use.
--
-- Option A: SnowSQL
-- -----------------
--   snowsql \
--     -a <your_account_identifier> \
--     -u KAFKA_USER \
--     --private-key-path keys/rsa_key.p8 \
--     -d INTERACTIVE_DEMO \
--     -s TPCH_INTERACTIVE \
--     -r KAFKA_CONNECTOR_ROLE \
--     -q "SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA()"
--
--   Expected output:
--     CURRENT_USER()  | CURRENT_ROLE()        | CURRENT_DATABASE() | CURRENT_SCHEMA()
--     KAFKA_USER      | KAFKA_CONNECTOR_ROLE  | INTERACTIVE_DEMO   | TPCH_INTERACTIVE
--
-- Option B: Snowflake CLI (snow)
-- ------------------------------
--   First, add a connection to ~/.snowflake/connections.toml:
--
--     [kafka_user]
--     account = "<your_account_identifier>"
--     user = "KAFKA_USER"
--     authenticator = "SNOWFLAKE_JWT"
--     private_key_file = "keys/rsa_key.p8"
--     role = "KAFKA_CONNECTOR_ROLE"
--     database = "INTERACTIVE_DEMO"
--     schema = "TPCH_INTERACTIVE"
--
--   Then test:
--     snow sql -c kafka_user -q "SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA()"
--
-- Option C: Python (snowflake-connector-python)
-- ----------------------------------------------
--   python3 -c "
--   from cryptography.hazmat.primitives import serialization
--   import snowflake.connector
--
--   with open('keys/rsa_key.p8', 'rb') as f:
--       private_key = serialization.load_pem_private_key(f.read(), password=None)
--
--   private_key_bytes = private_key.private_bytes(
--       encoding=serialization.Encoding.DER,
--       format=serialization.PrivateFormat.PKCS8,
--       encryption_algorithm=serialization.NoEncryption()
--   )
--
--   conn = snowflake.connector.connect(
--       account='<your_account_identifier>',
--       user='KAFKA_USER',
--       private_key=private_key_bytes,
--       role='KAFKA_CONNECTOR_ROLE',
--       database='INTERACTIVE_DEMO',
--       schema='TPCH_INTERACTIVE'
--   )
--   cur = conn.cursor()
--   cur.execute('SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA()')
--   print(cur.fetchone())
--
--   # Test INSERT permission
--   cur.execute('SELECT COUNT(*) FROM ORDERS_INTERACTIVE')
--   print(f'Row count: {cur.fetchone()[0]}')
--
--   conn.close()
--   print('SUCCESS: KAFKA_USER connectivity verified!')
--   "
--
-- Troubleshooting:
--   - "JWT token is invalid": Key mismatch — re-run Part 3 with correct public key
--   - "Insufficient privileges": Re-run Part 1 grants
--   - "User not found": Re-run Part 2
--   - "Connection refused": Check account identifier format (orgname-acctname)

-- =============================================================================
-- Cleanup (run only when done with the demo)
-- =============================================================================
-- DROP USER IF EXISTS KAFKA_USER;
-- DROP ROLE IF EXISTS KAFKA_CONNECTOR_ROLE;


-- run the data generator
--python3 generate_orders_data.py --rate 6500 --duration 10
--python3 generate_orders_data.py --rate 33800 --duration 10
--python3 generate_orders_data.py --rate 33800 --duration 10