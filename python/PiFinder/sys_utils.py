import os
import glob
import json
import re
from typing import Dict, Any
import time

import pam
import requests
import sh

import socket
from PiFinder import utils
import logging

BACKUP_PATH = "/home/pifinder/PiFinder_data/PiFinder_backup.zip"

logger = logging.getLogger("SysUtils")


class Network:
    """
    Provides wifi network info
    """

    def __init__(self):
        self.wifi_txt = f"{utils.pifinder_dir}/wifi_status.txt"
        logger.info("SYS: Wifi loc "+self.wifi_txt)
        try :
            with open(self.wifi_txt, "r") as wifi_f:
                self._wifi_mode = wifi_f.read()
        except Exception:            
            logger.info("File open error : " + self.wifi_txt)

        self.populate_wifi_networks()

    def populate_wifi_networks(self) -> None:
        self._wifi_networks = []

        directory_path = "/etc/NetworkManager/system-connections"  # Replace with the actual directory path
        entries = os.listdir(directory_path)
        files_only = [entry for entry in entries if os.path.isfile(os.path.join(directory_path, entry))]
        contents = []
        for entry in files_only:
            try:
                if Network.isAP(f"{directory_path}/{entry}") != True :
                    sh.sudo("cp",f"{directory_path}/{entry}", "/tmp/test")
                    sh.sudo("chmod","777", "/tmp/test")

                    try : 
                        with open("/tmp/test", "r") as conf:
                            contents.extend(conf.readlines())
                    except Exception:            
                        logger.info("File open error : /tmp/test")

                    sh.sudo("rm", "/tmp/test")
            except IOError as e:
                logger.error(f"Error reading wpa_supplicant.conf: {e}")

        self._wifi_networks = Network._parse_networkmanager(contents)

    @staticmethod
    def _parse_networkmanager(contents: list[str]) -> list:
        wifi_networks = []
        network_dict: Dict[str, Any] = {}
        network_id = 0
        in_network_block = False
        for line in contents:
            line = line.strip()
            if line.startswith("[connection]"):
                in_network_block = True
                network_dict = {
                    "id": network_id,
                    "ssid": None,
                    "psk": None,
                    "key_mgmt": None,
                    "uuid": None,
                }

            elif line == "[proxy]" and in_network_block:
                in_network_block = False
                wifi_networks.append(network_dict)
                network_id += 1

            elif in_network_block:
                match = re.match(r"(\w+)=(.+)", line)
                if match:
                    key, value = match.groups()
                    if key in network_dict:
                        network_dict[key] = value.strip('"')
        return wifi_networks


    @staticmethod
    def _parse_wpa_supplicant(contents: list[str]) -> list:
        """
        Parses wpa_supplicant.conf to get current config
        """
        wifi_networks = []
        network_dict: Dict[str, Any] = {}
        network_id = 0
        in_network_block = False
        for line in contents:
            line = line.strip()
            if line.startswith("network={"):
                in_network_block = True
                network_dict = {
                    "id": network_id,
                    "ssid": None,
                    "psk": None,
                    "key_mgmt": None,
                    "uuid": None,
                }

            elif line == "}" and in_network_block:
                in_network_block = False
                wifi_networks.append(network_dict)
                network_id += 1

            elif in_network_block:
                match = re.match(r"(\w+)=(.+)", line)
                if match:
                    key, value = match.groups()
                    if key in network_dict:
                        network_dict[key] = value.strip('"')

        return wifi_networks

    def get_wifi_networks(self):
        return self._wifi_networks

    def delete_wifi_network(self, network_uuid):
        """
        Immediately deletes a wifi network
        """
        directory_path = "/etc/NetworkManager/system-connections"  # Replace with the actual directory path
        entries = os.listdir(directory_path)
        files_only = [entry for entry in entries if os.path.isfile(os.path.join(directory_path, entry))]
        contents = ""
        for entry in files_only:
            try:
                if Network.isAP(f"{directory_path}/{entry}") != True :
                    sh.sudo("cp",f"{directory_path}/{entry}", "/tmp/test")
                    sh.sudo("chmod","777", "/tmp/test")
                    try : 
                        with open("/tmp/test", "r") as conf:
                            contents = conf.read()
                            if network_uuid in contents:
                                sh.sudo("rm",f"{directory_path}/{entry}")
                    except Exception:            
                        logger.info("File open error : /tmp/test")
                    
                    sh.sudo("rm", "/tmp/test")
            except IOError as e:
                logger.error(f"Error reading wpa_supplicant.conf: {e}")
        
        self.populate_wifi_networks()
        

    def add_wifi_network(self, ssid, key_mgmt, psk=None):
        """
        Add a wifi network
        """
        '''if self._wifi_mode == "AP":
            self.remove_ap()
            sh.sudo("nmcli","connection", "add", "type", "wifi", "ifname", "wlan0", "con-name", ssid, "ssid", ssid, "mode", "ap")
            sh.sudo("nmcli","connection", "modify", ssid, "connection.autoconnect", "yes")
            sh.sudo("nmcli","connection", "modify", ssid, "connection.autoconnect-priority", "1")
            with open('/tmp/switch-ap.sh', 'w') as f:
                f.write("#! /usr/bin/bash\n")
                f.write("nmcli connection up "+ssid+"\n")
                f.write('echo -n "AP" > /home/pifinder/PiFinder5/wifi_status.txt')
            
            sh.sudo("cp","/tmp/switch-ap.sh","/home/pifinder/PiFinder5/switch-ap.sh")

        else:'''

        sh.sudo("nmcli","connection", "add", "type", "wifi", "ifname", "wlan0", "con-name", ssid, "ssid", ssid, "mode", "infrastructure")
        sh.sudo("nmcli","connection", "modify", ssid, "connection.autoconnect", "yes")
        sh.sudo("nmcli","connection", "modify", ssid, "connection.autoconnect-priority", "0")

        if key_mgmt == "WPA-PSK":
            sh.sudo("nmcli","connection", "modify", ssid, "wifi-sec.key-mgmt", "wpa-psk")
            sh.sudo("nmcli","connection", "modify", ssid, "wifi-sec.psk", psk) 


        self.populate_wifi_networks()
        
        if self._wifi_mode == "Client":

            Network.set_client_priority("1")
            Network.set_ap_priority("0")
            
            sh.sudo("/home/pifinder/PiFinder5/switch-cli.sh")

    def set_client_priority(flag):
        
        directory_path = "/etc/NetworkManager/system-connections"  # Replace with the actual directory path
        entries = os.listdir(directory_path)
        files_only = [entry for entry in entries if os.path.isfile(os.path.join(directory_path, entry))]

        for entry in files_only:
            
            if Network.isAP(f"{directory_path}/{entry}") == False:
                sh.sudo("cp",f"{directory_path}/{entry}", "/tmp/test")
                sh.sudo("chmod","777", "/tmp/test")
                logger.info("SYS: Open /tmp/test")
                try : 
                    with open("/tmp/test", "r") as conf:
                        contents = conf.readlines()
                        for line in contents:
                            line = line.strip()
                            logger.info("SYS: Read line")
                            match = re.match(r"(\w+)=(.+)", line)
                            if match:
                                key, value = match.groups()
                                logger.info("SYS: Matched " + key)
                                if key == "ssid" :
                                    sh.sudo("nmcli","connection", "modify", value, "connection.autoconnect-priority", flag)
                except Exception:            
                    logger.info("File open error : /tmp/test")

                sh.sudo("rm", "/tmp/test")

    def set_ap_priority(flag):
        directory_path = "/etc/NetworkManager/system-connections"  # Replace with the actual directory path
        entries = os.listdir(directory_path)
        files_only = [entry for entry in entries if os.path.isfile(os.path.join(directory_path, entry))]

        for entry in files_only:
            if Network.isAP(f"{directory_path}/{entry}") == True:
                sh.sudo("cp",f"{directory_path}/{entry}", "/tmp/test")
                sh.sudo("chmod","777", "/tmp/test")

                try: 
                    with open("/tmp/test", "r") as conf:
                        contents = conf.readlines()
                        for line in contents:
                            line = line.strip()
                            match = re.match(r"(\w+)=(.+)", line)
                            if match:
                                key, value = match.groups()
                                if key == "ssid" :
                                    sh.sudo("nmcli","connection", "modify", value, "connection.autoconnect-priority", flag)
                except Exception:            
                    logger.info("File open error : /tmp/test")

                sh.sudo("rm", "/tmp/test")

    def remove_ap(self):
        directory_path = "/etc/NetworkManager/system-connections"  # Replace with the actual directory path
        entries = os.listdir(directory_path)
        files_only = [entry for entry in entries if os.path.isfile(os.path.join(directory_path, entry))]

        for entry in files_only:
            if Network.isAP(f"{directory_path}/{entry}") :
                sh.sudo("rm",f"{directory_path}/{entry}")
                time.sleep(1)

    def isAP(file):
        sh.sudo("cp", file, "/tmp/test")
        sh.sudo("chmod","777", "/tmp/test")
        try : 
            with open("/tmp/test", "r") as conf:
                for line in conf:
                    if line.startswith("mode="):
                        val = line[5:-1]
                        if val == "ap" :
                            return True
        except Exception:            
            logger.info("File open error : /tmp/test")

        
        sh.sudo("rm", "/tmp/test")
        
        return False

    def get_ap_name(self):
        directory_path = "/etc/NetworkManager/system-connections"  # Replace with the actual directory path
        entries = os.listdir(directory_path)
        files_only = [entry for entry in entries if os.path.isfile(os.path.join(directory_path, entry))]

        for entry in files_only:
            if Network.isAP(f"{directory_path}/{entry}") :
                sh.sudo("cp",f"{directory_path}/{entry}", "/tmp/test")
                sh.sudo("chmod","777", "/tmp/test")

                try :
                    with open("/tmp/test", "r") as conf:
                        contents = conf.readlines()
                        for line in contents:
                            line = line.strip()
                            match = re.match(r"(\w+)=(.+)", line)
                            if match:
                                key, value = match.groups()
                                if key == "ssid" :
                                    sh.sudo("rm", "/tmp/test")
                                    return value
                except Exception:            
                    logger.info("File open error : /tmp/test")

                sh.sudo("rm", "/tmp/test")

        return "UNKN"

    def set_ap_name(self, ap_name):
        if ap_name == self.get_ap_name():
            return
        
        ap = self.get_ap_name()

        if ap != "UNKN" :
            sh.sudo("nmcli","connection", "modify", ap, "ssid", ap_name) 
            sh.sudo("nmcli","connection", "modify", ap, "con-name", ap_name) 
            #directory_path = "/etc/NetworkManager/system-connections"  # Replace with the actual directory path
            #sh.sudo("mv",directory_path+"/"+ap+".nmconnection",directory_path+"/"+ap_name+".nmconnection")
            #time.sleep(1)
            #sh.sudo("rm",directory_path+"/"+ap+".nmconnection")
            time.sleep(1)

            if self._wifi_mode != "Client":
                Network.set_client_priority("0")
                Network.set_ap_priority("1")
                go_wifi_ap()

    def get_host_name(self):
        return socket.gethostname()

    def get_connected_ssid(self) -> str:
        """
        Returns the SSID of the connected wifi network or
        None if not connected or in AP mode
        """
        if self.wifi_mode() == "AP":
            return ""
        # get output from iwgetid
        try:
            iwgetid = sh.Command("iwgetid")
            _t = iwgetid(_ok_code=(0, 255)).strip()
            return _t.split(":")[-1].strip('"')
        except sh.CommandNotFound:
            return "ssid_not_found"

    def set_host_name(self, hostname) -> None:
        if hostname == self.get_host_name():
            return
        _result = sh.sudo("hostnamectl", "set-hostname", hostname)
        self._update_etc_hosts(hostname)

    @staticmethod
    def _rewrite_hosts(contents: str, new_hostname: str) -> str:
        """
        Rewrite the Debian-convention ``127.0.1.1`` line in /etc/hosts to point
        at ``new_hostname``. Preserves indentation, the IP, and any trailing
        aliases/comments. If no ``127.0.1.1`` line exists, appends one so that
        ``sudo`` can still resolve the host.
        """
        lines = contents.splitlines(keepends=True)
        pattern = re.compile(r"^(\s*127\.0\.1\.1\s+)\S+(.*)$")
        replaced = False
        for i, line in enumerate(lines):
            match = pattern.match(line)
            if match:
                eol = "\n" if line.endswith("\n") else ""
                lines[i] = f"{match.group(1)}{new_hostname}{match.group(2)}{eol}"
                replaced = True
                break
        if not replaced:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(f"127.0.1.1\t{new_hostname}\n")
        return "".join(lines)

    def _update_etc_hosts(self, new_hostname: str) -> None:
        try:
            with open("/etc/hosts", "r") as hosts_f:
                contents = hosts_f.read()
        except IOError as e:
            logger.error(f"Error reading /etc/hosts: {e}")
            return
        new_contents = Network._rewrite_hosts(contents, new_hostname)
        with open("/tmp/hosts", "w") as new_hosts:
            new_hosts.write(new_contents)
        sh.sudo("cp", "/tmp/hosts", "/etc/hosts")

    def wifi_mode(self):
        return self._wifi_mode

    def set_wifi_mode(self, mode):
        if mode == self._wifi_mode:
            return
        if mode == "AP":
            go_wifi_ap()

        if mode == "Client":
            go_wifi_cli()

    def local_ip(self):
        if self._wifi_mode == "AP":
            return "10.10.10.1"

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.255.255.255", 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = "NONE"
        finally:
            s.close()
        return ip


def go_wifi_ap():
    logger.info("SYS: Switching to AP")
    Network.set_client_priority("0")
    Network.set_ap_priority("1")
    try :
        with open(f"{utils.pifinder_dir}/wifi_status.txt", 'w') as f:
            logger.info("Set AP")
            f.write("AP")
    except Exception:            
        logger.info("File open error : " + f"{utils.pifinder_dir}/wifi_status.txt")
    time.sleep(1)
    return True


def go_wifi_cli():
    logger.info("SYS: Switching to Client")
    Network.set_client_priority("1")
    Network.set_ap_priority("0")
    try :
        with open(f"{utils.pifinder_dir}/wifi_status.txt", 'w') as f:
            logger.info("Set Client")
            f.write("Client")
    except Exception:            
        logger.info("File open error : " + f"{utils.pifinder_dir}/wifi_status.txt")
    time.sleep(1)
    return True


def remove_backup():
    """
    Removes backup file
    """
    sh.sudo("rm", BACKUP_PATH, _ok_code=(0, 1))


def backup_userdata():
    """
    Back up userdata to a single zip file for later
    restore.  Returns the path to the zip file.

    Backs up:
        config.json
        observations.db
        obslist/*
    """

    remove_backup()

    _zip = sh.Command("zip")
    _zip(
        BACKUP_PATH,
        "/home/pifinder/PiFinder_data/config.json",
        "/home/pifinder/PiFinder_data/observations.db",
        glob.glob("/home/pifinder/PiFinder_data/obslists/*"),
    )

    return BACKUP_PATH


def restore_userdata(zip_path):
    """
    Compliment to backup_userdata
    restores userdata
    OVERWRITES existing data!
    """
    sh.unzip("-d", "/", "-o", zip_path)


def restart_pifinder() -> None:
    """
    Uses systemctl to restart the PiFinder
    service
    """
    logger.info("SYS: Restarting PiFinder")
    sh.sudo("systemctl", "restart", "pifinder")


def restart_system() -> None:
    """
    Restarts the system
    """
    logger.info("SYS: Initiating System Restart")
    sh.sudo("shutdown", "-r", "now")


def shutdown() -> None:
    """
    shuts down the system
    """
    logger.info("SYS: Initiating Shutdown")
    sh.sudo("shutdown", "now")


def update_software():
    """
    Uses systemctl to git pull and then restart
    service
    """
    logger.info("SYS: Running update")
    sh.bash("/home/pifinder/PiFinder5/pifinder_update.sh")
    return True


def verify_password(username, password):
    """
    Checks the provided password against the provided user
    password
    """
    result = sh.su(username, "-c", "echo", _in=f"{password}\n", _ok_code=(0, 1))
    if result.exit_code == 0:
        return True
    else:
        return False


def change_password(username, current_password, new_password):
    """
    Changes the PiFinder User password
    """
    result = sh.passwd(
        username,
        _in=f"{current_password}\n{new_password}\n{new_password}\n",
        _ok_code=(0, 10),
    )

    if result.exit_code == 0:
        return True
    else:
        return False


def switch_cam_imx477() -> None:
    logger.info("SYS: Switching cam to imx477")
    sh.sudo("python", "-m", "PiFinder.switch_camera", "imx477")


def switch_cam_imx296() -> None:
    logger.info("SYS: Switching cam to imx296")
    sh.sudo("python", "-m", "PiFinder.switch_camera", "imx296")


def switch_cam_imx462() -> None:
    logger.info("SYS: Switching cam to imx462")
    sh.sudo("python", "-m", "PiFinder.switch_camera", "imx462")


def check_and_sync_gpsd_config(baud_rate: int) -> bool:
    """
    Checks if GPSD configuration matches the desired baud rate,
    and updates it only if necessary.

    Args:
        baud_rate: The desired baud rate (9600 or 115200)

    Returns:
        True if configuration was updated, False if already correct
    """
    logger.info(f"SYS: Checking GPSD config for baud rate {baud_rate}")

    try:
        # Read current config
        with open("/etc/default/gpsd", "r") as f:
            content = f.read()

        # Determine expected GPSD_OPTIONS
        if baud_rate == 115200:
            # NOTE: the space before -s in the next line is really needed
            expected_options = 'GPSD_OPTIONS=" -s 115200"'
        else:
            expected_options = 'GPSD_OPTIONS=""'

        # Check if update is needed
        current_match = re.search(r"^GPSD_OPTIONS=.*$", content, re.MULTILINE)
        if current_match:
            current_options = current_match.group(0)
            if current_options == expected_options:
                logger.info("SYS: GPSD config already correct, no update needed")
                return False

        # Update is needed
        logger.info(f"SYS: GPSD config mismatch, updating to {expected_options}")
        update_gpsd_config(baud_rate)
        return True

    except Exception as e:
        logger.error(f"SYS: Error checking/syncing GPSD config: {e}")
        return False


def update_gpsd_config(baud_rate: int) -> None:
    """
    Updates the GPSD configuration file with the specified baud rate
    and restarts the GPSD service.

    Args:
        baud_rate: The baud rate to configure (9600 or 115200)
    """
    logger.info(f"SYS: Updating GPSD config with baud rate {baud_rate}")

    try:
        # Read the current config
        with open("/etc/default/gpsd", "r") as f:
            lines = f.readlines()

        # Update GPSD_OPTIONS line
        updated_lines = []
        for line in lines:
            if line.startswith("GPSD_OPTIONS="):
                if baud_rate == 115200:
                    # NOTE: the space before -s in the next line is really needed
                    updated_lines.append('GPSD_OPTIONS=" -s 115200"\n')
                else:
                    updated_lines.append('GPSD_OPTIONS=""\n')
            else:
                updated_lines.append(line)

        # Write the updated config to a temporary file
        with open("/tmp/gpsd.conf", "w") as f:
            f.writelines(updated_lines)

        # Copy the temp file to the actual location with sudo
        sh.sudo("cp", "/tmp/gpsd.conf", "/etc/default/gpsd")

        # Restart GPSD service
        sh.sudo("systemctl", "restart", "gpsd")

        logger.info("SYS: GPSD configuration updated and service restarted")

    except Exception as e:
        logger.error(f"SYS: Error updating GPSD config: {e}")
        raise



def is_mountcontrol_active() -> bool:
    """
    Returns True if mount control service is active
    """
    status = sh.sudo("systemctl", "is-active", "indiwebmanager.service", _ok_code=(0, 3))
    if status.exit_code == 0:
        return True
    else:
        return False


def mountcontrol_activate() -> None:
    """
    Activates the mount control service
    """
    logger.info("SYS: Activating Mount Control")
    sh.sudo("systemctl", "enable", "--now", "indiwebmanager.service")
    sh.sudo("shutdown", "-r", "now")


def mountcontrol_deactivate() -> None:
    """
    Deactivates the mount control service
    """
    logger.info("SYS: Deactivating Mount Control")
    sh.sudo("systemctl", "disable", "--now", "indiwebmanager.service")
    sh.sudo("shutdown", "-r", "now")


# ---------------------------------------------------------------------------
# NixOS migration
# ---------------------------------------------------------------------------

MIGRATION_PROGRESS_FILE = "/tmp/nixos_migration_progress"
MIGRATION_SCRIPT = "/home/pifinder/PiFinder/python/scripts/nixos_migration.sh"


def _fetch_migration_sha256(version_info: dict) -> str:
    """Fetch SHA256 from sidecar URL, falling back to hardcoded value."""
    sha256_url = version_info.get("migration_sha256_url", "")
    if sha256_url:
        try:
            resp = requests.get(sha256_url, timeout=15)
            if resp.status_code == 200:
                sha256 = resp.text.strip().split()[0]
                logger.info(f"SYS: Fetched migration SHA256: {sha256[:16]}...")
                return sha256
            logger.warning(f"SYS: SHA256 fetch returned {resp.status_code}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"SYS: Failed to fetch SHA256: {e}")

    sha256 = version_info.get("migration_sha256", "")
    if sha256:
        logger.info("SYS: Using hardcoded migration SHA256")
    return sha256


def start_nixos_migration(version_info: dict) -> None:
    """
    Start the NixOS migration process in the background.

    Raises ValueError if migration_url or a migration SHA256 cannot be
    obtained — an in-place OS replacement must not run without checksum
    verification.
    """
    url = version_info.get("migration_url", "")
    if not url:
        raise ValueError("Missing migration_url")
    sha256 = _fetch_migration_sha256(version_info)
    if not sha256:
        raise ValueError(
            "No migration SHA256 available (neither migration_sha256_url nor "
            "migration_sha256 produced a value); refusing to migrate without "
            "checksum verification"
        )
    display_class = str(version_info.get("display_class", ""))
    display_resolution_value = version_info.get("display_resolution", "")
    if isinstance(display_resolution_value, (list, tuple)):
        display_resolution = "x".join(str(part) for part in display_resolution_value)
    else:
        display_resolution = str(display_resolution_value)

    logger.info(f"SYS: Starting NixOS migration to {version_info.get('version', '?')}")

    with open(MIGRATION_PROGRESS_FILE, "w") as f:
        json.dump({"percent": 0, "status": "Starting..."}, f)

    def _log_output(line):
        logger.info(f"SYS: migration: {line.strip()}")

    def _log_error(line):
        logger.error(f"SYS: migration: {line.strip()}")

    def _on_done(cmd, success, exit_code):
        if not success:
            logger.error(f"SYS: Migration script failed with exit code {exit_code}")

    try:
        sh.bash(
            MIGRATION_SCRIPT,
            url,
            sha256,
            MIGRATION_PROGRESS_FILE,
            display_class,
            display_resolution,
            _bg=True,
            _bg_exc=False,
            _out=_log_output,
            _err=_log_error,
            _done=_on_done,
        )
    except Exception as e:
        logger.error(f"SYS: Migration failed to start: {e}")
        raise


def get_migration_progress() -> Dict[str, Any]:
    """
    Read current migration progress from the progress file.
    """
    try:
        with open(MIGRATION_PROGRESS_FILE, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
