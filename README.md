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
