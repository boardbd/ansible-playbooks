# Ansible Playbooks

A collection of Ansible playbooks and roles for infrastructure automation and configuration management.

## Directory Structure

```
.
├── ansible.cfg          # Ansible configuration
├── requirements.yml     # Galaxy role/collection dependencies
├── inventory/
│   └── hosts            # Inventory of managed hosts
├── group_vars/
│   └── all.yml          # Variables applied to all hosts
├── host_vars/           # Per-host variable files
├── playbooks/
│   └── site.yml         # Master playbook
└── roles/               # Reusable Ansible roles
```

## Prerequisites

- [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/) >= 2.12
- Python >= 3.8
- SSH access to managed hosts

## Quick Start

### 1. Install Dependencies

```bash
pip install ansible
ansible-galaxy install -r requirements.yml
```

### 2. Configure Inventory

Edit `inventory/hosts` to add your managed hosts:

```ini
[webservers]
web1 ansible_host=192.168.1.10

[dbservers]
db1 ansible_host=192.168.1.20
```

### 3. Run the Master Playbook

```bash
ansible-playbook playbooks/site.yml
```

### 4. Run Against Specific Hosts

```bash
ansible-playbook playbooks/site.yml --limit webservers
```

## Playbooks

### NX-OS Software Upgrade (`playbooks/nxos_upgrade.yml`)

Automates Cisco NX-OS software upgrades on Nexus switches with full validation.

**Workflow:**

1. **Pre-checks** — gather current version, verify bootflash space, save/backup config
2. **Image transfer** — SCP the target image to bootflash (skipped if already present)
3. **Verification** — MD5 checksum validation
4. **Install** — set boot variable and trigger upgrade via `nxos_install_os`
5. **Reload & wait** — wait for the switch to come back online
6. **Post-checks** — verify target version is running, check module status, save config
7. **Cleanup** (optional) — delete the old image from bootflash

**Setup:**

1. Install required collections:
   ```bash
   ansible-galaxy collection install -r requirements.yml
   ```

2. Add switches to `inventory/hosts` under the `[nxos]` group:
   ```ini
   [nxos]
   nxos_switch1 ansible_host=192.168.1.50
   ```

3. Edit `group_vars/nxos.yml` with your target image, MD5, SCP server, and credentials.
   Encrypt sensitive values with Ansible Vault:
   ```bash
   ansible-vault encrypt_string 'mypassword' --name 'scp_password'
   ```

4. Run the upgrade:
   ```bash
   ansible-playbook playbooks/nxos_upgrade.yml
   ```

5. Optionally delete the old image after a successful upgrade:
   ```bash
   ansible-playbook playbooks/nxos_upgrade.yml -e "delete_old_image=true"
   ```

**ISSU (non-disruptive upgrade):**

Set `nxos_issu` in `group_vars/nxos.yml` to `desired` or `required` for In Service Software Upgrade (supported on N5k, N7k, N9k).

---

### LibreNMS Dynamic Inventory (`inventory/librenms.py`)

Pulls devices directly from your LibreNMS instance and builds Ansible inventory groups automatically.

**Groups created:**

| Prefix | Source | Example |
|--------|--------|---------|
| `os_` | Device OS | `os_nxos`, `os_linux` |
| `type_` | Device type | `type_network`, `type_server` |
| `location_` | Location string | `location_dc1` |
| `hw_` | Hardware model | `hw_nexus_9000` |
| `group_` | LibreNMS device groups | `group_core_switches` |

**Host variables set automatically:**

- `ansible_host` — device hostname/IP
- `ansible_network_os` / `ansible_connection` — auto-detected for Cisco NX-OS and IOS
- `librenms_device_id`, `librenms_os`, `librenms_hardware`, `librenms_serial`, `librenms_version`, `librenms_location`, `librenms_status`, `librenms_uptime`

**Setup:**

1. Install Python dependencies:
   ```bash
   pip install requests pyyaml
   ```

2. Edit `inventory/librenms.yml` with your LibreNMS URL and API token, or set environment variables:
   ```bash
   export LIBRENMS_URL="https://librenms.example.com/api/v0"
   export LIBRENMS_TOKEN="your-api-token"
   ```

3. Test the inventory:
   ```bash
   ./inventory/librenms.py --list
   ansible-inventory -i inventory/librenms.py --graph
   ```

4. Use with any playbook:
   ```bash
   ansible-playbook -i inventory/librenms.py playbooks/nxos_upgrade.yml
   ```

**Configuration options** are documented in `inventory/librenms.yml` (hostname field, grouping, filters, etc.).

---

## Adding Roles

Create a new role with the standard structure:

```bash
ansible-galaxy role init roles/<role_name>
```

Then reference it in the appropriate play within `playbooks/site.yml`.

## Using Ansible Vault

Encrypt sensitive variables:

```bash
ansible-vault create group_vars/vault.yml
ansible-playbook playbooks/site.yml --ask-vault-pass
```

## Contributing

1. Create a feature branch from `master`.
2. Add or modify playbooks/roles.
3. Test changes with `--check` (dry-run) mode before applying.
4. Submit a pull request.

## License

MIT
