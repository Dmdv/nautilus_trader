# Security Guide

This guide covers secure credential management for production trading systems.

---

## ⚠️ Critical Security Principles

1. **Never commit secrets to git**
2. **Never store mnemonics in plaintext for production**
3. **Always enable IP whitelisting on exchanges**
4. **Use separate API keys for data and trading**
5. **Rotate credentials regularly**

---

## Secrets Management Tiers

| Environment | Solution | Security Level |
|-------------|----------|----------------|
| **Development** | `.env` file | Basic |
| **Staging** | sops-encrypted files | Moderate |
| **Production** | HashiCorp Vault / AWS KMS | High |

---

## Development: .env Files

For local development only:

```bash
# Generate template
make config-template

# Copy to .env
cp .env.template .env

# Edit with your credentials
# NEVER commit .env to git
```

Example `.env`:

```bash
# Binance
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_secret_here
BINANCE_TESTNET=true

# Bybit
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_secret_here
BYBIT_TESTNET=true

# OKX
OKX_API_KEY=your_api_key_here
OKX_API_SECRET=your_secret_here
OKX_PASSPHRASE=your_passphrase_here
OKX_TESTNET=true

# dYdX (TESTNET ONLY - use hardware wallet for mainnet)
DYDX_MNEMONIC=word1 word2 word3 ... word24
DYDX_NETWORK=testnet
```

Verify `.env` is gitignored:

```bash
grep "\.env" .gitignore
# Should return: .env
```

---

## Staging: sops-encrypted Files

For pre-production environments, use [sops](https://github.com/getsops/sops):

### Setup

```bash
# Install sops
brew install sops  # macOS
# or
apt install sops   # Ubuntu

# Create age key for encryption
age-keygen -o ~/.config/sops/age/keys.txt

# Export public key
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt
```

### Encrypt Secrets

```bash
# Create secrets file
cat > secrets.yaml << EOF
binance:
  api_key: your_api_key
  api_secret: your_secret
bybit:
  api_key: your_api_key
  api_secret: your_secret
okx:
  api_key: your_api_key
  api_secret: your_secret
  passphrase: your_passphrase
EOF

# Encrypt
sops -e secrets.yaml > secrets.enc.yaml

# Delete plaintext
rm secrets.yaml

# Commit encrypted file (safe)
git add secrets.enc.yaml
```

### Decrypt at Runtime

```python
import subprocess
import yaml

def load_secrets():
    result = subprocess.run(
        ["sops", "-d", "secrets.enc.yaml"],
        capture_output=True,
        text=True
    )
    return yaml.safe_load(result.stdout)

secrets = load_secrets()
api_key = secrets["binance"]["api_key"]
```

---

## Production: HashiCorp Vault

For production systems, use HashiCorp Vault:

### Setup Vault

```bash
# Install Vault
brew install vault  # macOS

# Start dev server (for testing)
vault server -dev

# In production, use proper Vault deployment
```

### Store Secrets

```bash
# Enable KV secrets engine
vault secrets enable -path=trading kv-v2

# Store credentials
vault kv put trading/binance \
    api_key="your_api_key" \
    api_secret="your_secret"

vault kv put trading/bybit \
    api_key="your_api_key" \
    api_secret="your_secret"

vault kv put trading/okx \
    api_key="your_api_key" \
    api_secret="your_secret" \
    passphrase="your_passphrase"
```

### Retrieve at Runtime

```python
import hvac

def get_vault_client():
    return hvac.Client(
        url='https://vault.example.com',
        token=os.environ['VAULT_TOKEN']
    )

def get_binance_credentials():
    client = get_vault_client()
    secret = client.secrets.kv.v2.read_secret_version(
        path='binance',
        mount_point='trading'
    )
    return secret['data']['data']

creds = get_binance_credentials()
api_key = creds['api_key']
api_secret = creds['api_secret']
```

---

## Production: AWS Secrets Manager

Alternative for AWS environments:

### Store Secrets

```bash
aws secretsmanager create-secret \
    --name trading/binance \
    --secret-string '{"api_key":"xxx","api_secret":"yyy"}'
```

### Retrieve at Runtime

```python
import boto3
import json

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

creds = get_secret('trading/binance')
api_key = creds['api_key']
```

---

## dYdX: Special Handling Required

⚠️ **dYdX uses a mnemonic that provides FULL wallet control**

A compromised mnemonic means:
- Complete access to all funds
- Ability to transfer assets anywhere
- No way to revoke access

### Option 1: Hardware Wallet (Recommended)

Use Ledger or Trezor:

```python
# Connect via dYdX frontend
# Sign transactions with hardware device
# Private key never leaves hardware
```

### Option 2: AWS KMS

Store mnemonic in KMS, decrypt only at runtime:

```python
import boto3

def get_dydx_mnemonic():
    kms = boto3.client('kms')

    # Encrypted mnemonic (base64)
    encrypted = "AQICAHh..."

    response = kms.decrypt(
        CiphertextBlob=base64.b64decode(encrypted),
        KeyId='alias/dydx-mnemonic'
    )

    return response['Plaintext'].decode()

# Use only when needed, don't cache
mnemonic = get_dydx_mnemonic()
```

### Option 3: Vault with Short TTL

```python
def get_dydx_mnemonic():
    client = hvac.Client(url='https://vault.example.com')

    # Token with short TTL
    secret = client.secrets.kv.v2.read_secret_version(
        path='dydx',
        mount_point='trading'
    )

    return secret['data']['data']['mnemonic']
```

### Never Do This

```bash
# ❌ NEVER store mnemonic in plaintext .env for production
DYDX_MNEMONIC=word1 word2 word3 ... word24

# ❌ NEVER commit mnemonic to git
# ❌ NEVER log mnemonic
# ❌ NEVER send mnemonic over unencrypted channels
```

---

## IP Whitelisting

### Why It's Critical

Even if API keys are compromised, IP whitelisting prevents:
- Unauthorized trading from unknown locations
- Complete account takeover
- Funds extraction (for exchanges that support withdrawal via API)

### Binance

1. Go to https://www.binance.com/en/my/settings/api-management
2. Click "Edit restrictions" on your API key
3. Select "Restrict access to trusted IPs only"
4. Add your server's static IP(s)
5. Save

```bash
# Find your server's public IP
curl ifconfig.me
```

### Bybit

1. Go to https://www.bybit.com/app/user/api-management
2. Click "Edit" on your API key
3. Enable "IP Restrictions"
4. Add your server IPs
5. Save

### OKX

⚠️ OKX requires IP whitelist at key creation time:

1. Go to https://www.okx.com/account/my-api
2. Click "Create API key"
3. In "IP Whitelist" field, enter your server IPs (comma-separated)
4. Complete creation

**Note**: OKX IP whitelist cannot be modified after creation. You must delete and recreate the key.

### dYdX

dYdX uses wallet-based authentication, not API keys:
- No IP whitelisting available
- Security relies on mnemonic/private key protection
- Use hardware wallet for maximum security

### Verify Whitelisting

```bash
make ip-whitelist-verify
```

---

## API Key Permissions

### Principle of Least Privilege

Create separate keys for different purposes:

| Key Type | Permissions | Use Case |
|----------|-------------|----------|
| Data key | Read only | Market data, account info |
| Trade key | Trade + Read | Order execution |
| Full key | Trade + Withdraw | Never use for bots |

### Binance Permissions

- ✅ Enable: "Enable Reading", "Enable Spot & Margin Trading", "Enable Futures"
- ❌ Disable: "Enable Withdrawals", "Enable Internal Transfer"

### Bybit Permissions

- ✅ Enable: "Read", "Trade"
- ❌ Disable: "Withdraw", "Transfer"

### OKX Permissions

- ✅ Enable: "Read", "Trade"
- ❌ Disable: "Withdraw"

---

## Security Audit

Run a full security audit:

```bash
make security-audit
```

This checks:
- Exposed secrets in code
- `.env` gitignore status
- IP whitelist verification

---

## Credential Rotation

### When to Rotate

- Every 90 days (recommended)
- After employee departure
- After suspected compromise
- After security incident

### Rotation Process

```bash
make secrets-rotate
```

Follow the guided process for each exchange.

### Automated Rotation (Advanced)

For Vault, configure automatic rotation:

```hcl
resource "vault_generic_secret" "binance" {
  path = "trading/binance"

  # Rotate every 30 days
  lifecycle {
    create_before_destroy = true
  }
}
```

---

## Incident Response

### If Credentials Are Compromised

1. **Immediately** revoke/delete the compromised API key on the exchange
2. Check recent account activity for unauthorized trades
3. Create new API key with fresh credentials
4. Update all systems using the old credentials
5. Review how compromise occurred
6. Document incident

### If Mnemonic Is Compromised (dYdX)

1. **Immediately** transfer all funds to a new wallet
2. Generate new mnemonic
3. Update dYdX account to new wallet
4. Review how compromise occurred
5. Consider hardware wallet for future

---

## Security Checklist

Before going to production:

- [ ] API keys stored in Vault/KMS (not .env)
- [ ] IP whitelisting enabled on all exchanges
- [ ] Separate data and trade API keys
- [ ] dYdX using hardware wallet or KMS
- [ ] `.env` is gitignored
- [ ] No secrets in code or logs
- [ ] Secrets rotation schedule defined
- [ ] Incident response plan documented
- [ ] `make security-audit` passes

---

## Next Steps

1. **Set up secrets management** for your environment
2. **Enable IP whitelisting** on all exchanges
3. **Create separate API keys** for data and trading
4. **Configure exchange connections**: [CONFIGURATION.md](CONFIGURATION.md)
