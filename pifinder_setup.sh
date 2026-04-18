#!/usr/bin/bash
# Raspberry Pi OS bookworm required
# This script installs the PiFinder5 software on a prepared Raspberry Pi OS.
# See https://pifinder.readthedocs.io/en/release/software.html for more info.
#
# Fresh install (run as pifinder user):
#   wget -O /tmp/pifinder_setup.sh https://raw.githubusercontent.com/monovolt/PiFinderRPi5/release/pifinder_setup.sh && bash /tmp/pifinder_setup.sh


# Additional steps
# python3 -m pip config set global.break-system-packages true
# sudo apt remove python3-rpi.gpio 
# sudo apt remove libexif-dev sudo apt remove ibavdevice-dev libavcodec-dev libavformat-dev libswresample-dev 
# 
# pip3.10 install rpi-lgpio
# sudo apt install -y libcap-dev python3-picamera2
# pip3.10 install picamera2
# sudo vi /boot/firmware/config.txt
# dtoverlay=pwm-2chan,pin=13,func=4
# enable serial port using sudo raspi-config
# sudo vi /boot/firmware/config.txt
# enable_uart=1
# dtoverlay=uart2
# dtparam=uart2=on
# dtoverlay=imx290,clock-frequency=74250000 #IMX462

# sudo apt-get install gpsd gpsd-clients
# sudo vi /etc/default/gpsd
# # They need to be read/writeable, either by user gpsd or the group dialout.
# DEVICES="/dev/ttyAMA2"
# Other options you want to pass to gpsd
# GPSD_OPTIONS="-n"
# Automatically hot add/remove USB GPS devices via gpsdctl
# USBAUTO="true"
# Add dns=dnsmasq in /etc/NetworkManage/NetworkManager.conf

               
set -e

cd ~pifinder/

sudo apt-get install -y git python3-pip samba samba-common-bin dnsmasq hostapd dhcpd gpsd \
    libcap-dev python3-picamera2 python3-dev libatlas-base-dev

# RPi5: remove RPi.GPIO (incompatible) and use rpi-lgpio instead
sudo apt-get remove -y python3-rpi.gpio 2>/dev/null || true

if [[ -d PiFinder5/ ]]; then
    cd PiFinder5/ && git config pull.rebase false && git pull
else
    git clone --recursive --branch release https://github.com/monovolt/PiFinderRPi5.git PiFinder5
fi
cd ~/PiFinder5/python && python3 -m venv --system-site-packages .venv && source .venv/bin/activate && pip install -r requirements.txt
# rpi-lgpio must be force-installed in venv so it shadows the apt version and provides RPi.GPIO for RPi5
pip install --force-reinstall rpi-lgpio
# Remove any stale user-local RPi.GPIO that would override rpi-lgpio
rm -rf ~/.local/lib/python3.*/site-packages/RPi/GPIO ~/.local/lib/python3.*/site-packages/RPi.GPIO-*.dist-info 2>/dev/null || true

# Setup GPSD
sudo dpkg-reconfigure -plow gpsd
sudo cp ~/PiFinder5/pi_config_files/gpsd.conf /etc/default/gpsd

# data dirs
[[ -d ~/PiFinder_data ]] || \
mkdir ~/PiFinder_data
[[ -d ~/PiFinder_data/captures ]] || \
mkdir ~/PiFinder_data/captures
[[ -d ~/PiFinder_data/obslists ]] || \
mkdir ~/PiFinder_data/obslists
[[ -d ~/PiFinder_data/screenshots ]] || \
mkdir ~/PiFinder_data/screenshots
[[ -d ~/PiFinder_data/solver_debug_dumps ]] || \
mkdir ~/PiFinder_data/solver_debug_dumps
[[ -d ~/PiFinder_data/logs ]] || \
mkdir ~/PiFinder_data/logs
find ~/PiFinder_data -type d -exec chmod 755 {} \;

# Wifi config
#sudo cp ~/PiFinder5/pi_config_files/dhcpcd.* /etc
#sudo cp ~/PiFinder5/pi_config_files/dhcpcd.conf.sta /etc/dhcpcd.conf
#sudo cp ~/PiFinder5/pi_config_files/dnsmasq.conf /etc/dnsmasq.conf
#sudo cp ~/PiFinder5/pi_config_files/hostapd.conf /etc/hostapd/hostapd.conf
#echo -n "Client" > ~/PiFinder5/wifi_status.txt
#sudo systemctl unmask hostapd

# open permissisons on wpa_supplicant file so we can adjust network config
# sudo chmod 666 /etc/wpa_supplicant/wpa_supplicant.conf

# Samba config
sudo cp ~/PiFinder5/pi_config_files/smb.conf /etc/samba/smb.conf

# Hipparcos catalog
HIP_MAIN_DAT="/home/pifinder/PiFinder5/astro_data/hip_main.dat"
if [[ ! -e $HIP_MAIN_DAT ]]; then
    wget -O $HIP_MAIN_DAT https://cdsarc.cds.unistra.fr/ftp/cats/I/239/hip_main.dat
fi

# Enable interfaces
grep -q "dtparam=spi=on" /boot/config.txt || \
   echo "dtparam=spi=on" | sudo tee -a /boot/config.txt
grep -q "dtparam=i2c_arm=on" /boot/config.txt || \
   echo "dtparam=i2c_arm=on" | sudo tee -a /boot/config.txt
grep -q "dtparam=i2c_arm_baudrate=10000" /boot/config.txt || \
   echo "dtparam=i2c_arm_baudrate=10000" | sudo tee -a /boot/config.txt
grep -q "dtoverlay=pwm,pin=13,func=4" /boot/config.txt || \
   echo "dtoverlay=pwm,pin=13,func=4" | sudo tee -a /boot/config.txt
grep -q "dtoverlay=uart3" /boot/config.txt || \
   echo "dtoverlay=uart3" | sudo tee -a /boot/config.txt
# Note: camera types are added lateron by python/PiFinder5/switch_camera.py

# Disable unwanted services
sudo systemctl disable ModemManager

# Enable service
sudo cp /home/pifinder/PiFinder5/pi_config_files/pifinder.service /lib/systemd/system/pifinder.service
sudo cp /home/pifinder/PiFinder5/pi_config_files/pifinder_splash.service /lib/systemd/system/pifinder_splash.service
sudo systemctl daemon-reload
sudo systemctl enable pifinder
sudo systemctl enable pifinder_splash

echo "PiFinder setup complete, please restart the Pi"
