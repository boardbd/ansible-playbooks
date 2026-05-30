# Ansible Playbooks

A collection of Ansible playbooks and roles for infrastructure automation and configuration management.

## Directory Structure

```
.
├── ansible.cfg          # Ansible configuration
├── requirements.yml     # Galaxy role/collection dependencies
├── inventory/
│   ├── hosts            # Static inventory of managed hosts
│   ├── librenms.py      # LibreNMS dynamic inventory script
│   └── librenms.yml     # LibreNMS inventory configuration
├── group_vars/
│   ├── all.yml          # Variables applied to all hosts
│   └── nxos.yml         # NX-OS connection & upgrade variables
├── host_vars/           # Per-host variable files
├── playbooks/
│   ├── site.yml         # Master playbook
│   └── nxos_upgrade.yml # NX-OS upgrade playbook (uses nxos_upgrade role)
└── roles/
    └── nxos_upgrade/    # NX-OS upgrade role
        ├── defaults/main.yml   # Default variables
        ├── meta/main.yml       # Role metadata & dependencies
        └── tasks/
            ├── main.yml          # Orchestrator (block/rescue/always)
            ├── pre_checks.yml    # Version check, bootflash, config backup
            ├── transfer.yml      # SCP image transfer
            ├── verify.yml        # MD5 checksum validation
            ├── install.yml       # Boot variable & reload
            ├── post_checks.yml   # Version verification & module status
            ├── cleanup.yml       # Optional old image removal
            ├── notify_start.yml  # Slack: upgrade starting
            ├── notify_success.yml# Slack: upgrade succeeded
            └── notify_failure.yml# Slack: upgrade failed
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

Automates Cisco NX-OS software upgrades on Nexus switches using the `nxos_upgrade` role.

The playbook delegates all work to `roles/nxos_upgrade`, which splits the upgrade lifecycle into focused task files:

| Task file | Purpose |
|-----------|-----------------------------------------------|
| `pre_checks.yml` | Gather version, verify bootflash, backup config |
| `transfer.yml` | SCP image to bootflash (skipped if present) |
| `verify.yml` | MD5 checksum validation |
| `install.yml` | Set boot variable, trigger upgrade, wait for reload |
| `post_checks.yml` | Verify target version, check modules, save config |
| `cleanup.yml` | Delete old image (when `delete_old_image: true`) |
| `notify_*.yml` | Slack webhook notifications (start/success/failure) |

The role's `tasks/main.yml` orchestrates these files with `block/rescue/always` to guarantee Slack notifications are sent regardless of outcome.

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

**Slack Notifications:**

The playbook sends upgrade status to a Slack channel via incoming webhook:

| Event | Color | Emoji |
|-------|-------|-------|
| Upgrade starting | Blue | :rocket: |
| Upgrade succeeded | Green | :white_check_mark: |
| Upgrade failed | Red | :rotating_light: |

Each notification includes: hostname, previous version, target version, and image name. Failure notifications also include the failed task name and error message.

Setup:
1. Create an [incoming webhook](https://api.slack.com/messaging/webhooks) in your Slack workspace.
2. Set `slack_webhook_url` in `group_vars/nxos.yml` (encrypt with Vault).
3. Optionally set `slack_channel` to override the webhook's default channel.

To disable Slack notifications, leave `slack_webhook_url` empty or undefined.

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

See `roles/nxos_upgrade/` for a working example with defaults, metadata, and split task files.

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
