#!/usr/bin/env python3
"""
LibreNMS Dynamic Inventory Script for Ansible.

Queries the LibreNMS API to build an Ansible inventory, grouping devices
by OS, hardware type, device type, location, and LibreNMS device groups.

Configuration is read from a YAML file (default: librenms.yml in the same
directory as this script).

Usage:
    # List mode (Ansible calls this automatically):
    ./librenms.py --list

    # Host mode (returns host vars for a single host):
    ./librenms.py --host <hostname>

    # Specify an alternate config file:
    ./librenms.py --list --config /path/to/librenms.yml

Environment variables (override config file values):
    LIBRENMS_URL   - Base API URL (e.g. https://librenms.example.com/api/v0)
    LIBRENMS_TOKEN - API authentication token

Requires: requests, pyyaml
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("ERROR: 'requests' library is required. Install with: pip install requests")

try:
    import yaml
except ImportError:
    yaml = None


def load_config(config_path):
    """Load configuration from YAML file, with env-var overrides."""
    config = {
        "librenms_url": "",
        "librenms_token": "",
        "validate_certs": True,
        "timeout": 30,
        "group_by": ["os", "type", "location", "hardware", "device_groups"],
        "group_prefix": "",
        "hostname_field": "hostname",
        "ansible_host_field": "hostname",
        "include_disabled": False,
        "include_ignored": False,
        "host_vars": True,
    }

    if config_path and os.path.isfile(config_path):
        if yaml is None:
            sys.exit(
                "ERROR: 'pyyaml' library is required to read config files. "
                "Install with: pip install pyyaml"
            )
        with open(config_path, "r") as f:
            file_config = yaml.safe_load(f) or {}
        config.update(file_config)

    if os.environ.get("LIBRENMS_URL"):
        config["librenms_url"] = os.environ["LIBRENMS_URL"]
    if os.environ.get("LIBRENMS_TOKEN"):
        config["librenms_token"] = os.environ["LIBRENMS_TOKEN"]

    config["librenms_url"] = config["librenms_url"].rstrip("/")

    if not config["librenms_url"] or not config["librenms_token"]:
        sys.exit(
            "ERROR: librenms_url and librenms_token are required.\n"
            "Set them in the config file or via LIBRENMS_URL / LIBRENMS_TOKEN env vars."
        )

    return config


def api_request(config, endpoint):
    """Make an authenticated GET request to the LibreNMS API."""
    url = f"{config['librenms_url']}/{endpoint.lstrip('/')}"
    headers = {
        "X-Auth-Token": config["librenms_token"],
        "Content-Type": "application/json",
    }
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=config["timeout"],
            verify=config["validate_certs"],
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        sys.stderr.write(f"ERROR: Cannot connect to LibreNMS at {url}\n")
    except requests.exceptions.Timeout:
        sys.stderr.write(f"ERROR: Request timed out: {url}\n")
    except requests.exceptions.HTTPError as e:
        sys.stderr.write(f"ERROR: HTTP {e.response.status_code} from {url}\n")
    except ValueError:
        sys.stderr.write(f"ERROR: Invalid JSON from {url}\n")
    return None


def sanitize_group_name(name):
    """Convert a string into a valid Ansible group name."""
    if not name:
        return "unknown"
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_") or "unknown"


def add_host_to_group(inventory, group_name, hostname):
    """Add a host to a group in the inventory dict."""
    if group_name not in inventory:
        inventory[group_name] = {"hosts": [], "vars": {}, "children": []}
    if hostname not in inventory[group_name]["hosts"]:
        inventory[group_name]["hosts"].append(hostname)


def fetch_device_groups(config):
    """Fetch LibreNMS device groups and their members."""
    groups = {}
    data = api_request(config, "devicegroups")
    if not data:
        return groups

    device_groups = data.get("groups", [])
    for group in device_groups:
        group_id = group.get("id")
        group_name = group.get("name", f"group_{group_id}")

        members_data = api_request(config, f"devicegroups/{group_id}")
        if members_data:
            device_ids = set()
            for item in members_data.get("devices", []):
                device_id = item.get("device_id")
                if device_id is not None:
                    device_ids.add(int(device_id))
            groups[group_name] = device_ids

    return groups


def build_inventory(config):
    """Build the full Ansible inventory from LibreNMS."""
    inventory = {"_meta": {"hostvars": {}}, "all": {"hosts": [], "vars": {}, "children": []}}
    prefix = config.get("group_prefix", "")

    data = api_request(config, "devices")
    if not data:
        return inventory

    devices = data.get("devices", [])

    device_groups = {}
    if "device_groups" in config.get("group_by", []):
        device_groups = fetch_device_groups(config)

    for device in devices:
        if not config["include_disabled"] and device.get("disabled") == 1:
            continue
        if not config["include_ignored"] and device.get("ignore") == 1:
            continue

        hostname_field = config.get("hostname_field", "hostname")
        hostname = device.get(hostname_field) or device.get("hostname", "")
        if not hostname:
            continue

        ansible_host_field = config.get("ansible_host_field", "hostname")
        ansible_host = device.get(ansible_host_field) or hostname

        inventory["all"]["hosts"].append(hostname)

        if config.get("host_vars", True):
            hostvars = {"ansible_host": ansible_host}

            var_fields = {
                "librenms_device_id": "device_id",
                "librenms_os": "os",
                "librenms_version": "version",
                "librenms_hardware": "hardware",
                "librenms_serial": "serial",
                "librenms_sysname": "sysName",
                "librenms_type": "type",
                "librenms_location": "location",
                "librenms_status": "status",
                "librenms_uptime": "uptime",
            }

            for var_name, api_field in var_fields.items():
                value = device.get(api_field)
                if value is not None:
                    hostvars[var_name] = value

            os_name = device.get("os", "")
            if os_name:
                nxos_patterns = ["nxos", "cisco-nxos", "nx-os"]
                ios_patterns = ["ios", "cisco-ios", "iosxe", "cisco-iosxe"]
                if any(p in os_name.lower() for p in nxos_patterns):
                    hostvars["ansible_network_os"] = "cisco.nxos.nxos"
                    hostvars["ansible_connection"] = "ansible.netcommon.network_cli"
                elif any(p in os_name.lower() for p in ios_patterns):
                    hostvars["ansible_network_os"] = "cisco.ios.ios"
                    hostvars["ansible_connection"] = "ansible.netcommon.network_cli"

            inventory["_meta"]["hostvars"][hostname] = hostvars

        group_by = config.get("group_by", [])

        if "os" in group_by:
            os_val = device.get("os")
            if os_val:
                group_name = f"{prefix}os_{sanitize_group_name(os_val)}"
                add_host_to_group(inventory, group_name, hostname)

        if "type" in group_by:
            type_val = device.get("type")
            if type_val:
                group_name = f"{prefix}type_{sanitize_group_name(type_val)}"
                add_host_to_group(inventory, group_name, hostname)

        if "location" in group_by:
            location_val = device.get("location")
            if location_val:
                group_name = f"{prefix}location_{sanitize_group_name(location_val)}"
                add_host_to_group(inventory, group_name, hostname)

        if "hardware" in group_by:
            hw_val = device.get("hardware")
            if hw_val:
                group_name = f"{prefix}hw_{sanitize_group_name(hw_val)}"
                add_host_to_group(inventory, group_name, hostname)

        if "device_groups" in group_by:
            device_id = device.get("device_id")
            if device_id is not None:
                device_id = int(device_id)
                for group_name, member_ids in device_groups.items():
                    if device_id in member_ids:
                        safe_name = f"{prefix}group_{sanitize_group_name(group_name)}"
                        add_host_to_group(inventory, safe_name, hostname)

    return inventory


def get_host(config, hostname):
    """Return hostvars for a single host."""
    inventory = build_inventory(config)
    return inventory.get("_meta", {}).get("hostvars", {}).get(hostname, {})


def find_config_file(explicit_path):
    """Locate the config file — explicit path or default beside this script."""
    if explicit_path:
        return explicit_path
    script_dir = Path(__file__).resolve().parent
    default_path = script_dir / "librenms.yml"
    if default_path.is_file():
        return str(default_path)
    return None


def main():
    parser = argparse.ArgumentParser(description="LibreNMS dynamic inventory for Ansible")
    parser.add_argument("--list", action="store_true", help="List all hosts and groups")
    parser.add_argument("--host", type=str, help="Get variables for a specific host")
    parser.add_argument("--config", type=str, help="Path to config file (default: librenms.yml)")
    args = parser.parse_args()

    config_path = find_config_file(args.config)
    config = load_config(config_path)

    if args.host:
        result = get_host(config, args.host)
    elif args.list:
        result = build_inventory(config)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
