import os
import glob
import re
from typing import Dict, Any
import time

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
    # sh.sudo("systemctl", "start", "indiwebmanager.service")
    # We need to start the mount control process during startup, so reboot
    sh.sudo("shutdown", "-r", "now")


def mountcontrol_deactivate() -> None:
    """
    Deactivates the mount control service
    """
    logger.info("SYS: Deactivating Mount Control")
    sh.sudo("systemctl", "disable", "--now", "indiwebmanager.service")
    # sh.sudo("systemctl", "stop", "indiwebmanager.service")
    # We do NOT need to start the mount control process during startup, so reboot
    sh.sudo("shutdown", "-r", "now")