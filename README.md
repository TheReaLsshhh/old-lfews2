[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/TheReaLsshhh/old-lfews2) <--- **Click See Details**
# LFEWS Django Project

This project is built using Python's Django framework to monitor water levels through Modbus TCP/IP-connected sensors. Follow the steps below to properly set up and run the application.

---

## Requirements and Setup Instructions

1. **Install XAMPP**
   - Download and install XAMPP.
   - Create a MySQL database named: `old-lfews`.

2. **Install Python 3.13**
   - This project uses Python 3.13 (version at the time of development).
   - [Download Python 3.13](https://www.python.org/downloads/)

3. **Install Modbus Poll Application**
   - The Modbus Poll application was provided by the organization during development.
   - Setup:
     - Open Modbus Poll.
     - Go to `File > New > Connection > Connect`.
     - Under *Connection*, select `Modbus TCP/IP`.
     - Enter the IP address of your sensors or the desired IP address.

4. **Install PyCharm Community Edition or Preferred IDE**
   - [Download PyCharm Community](https://www.jetbrains.com/pycharm/download/)

5. **Install NSSM (Non-Sucking Service Manager)**
   - [Download NSSM](https://nssm.cc/download)
   - This is used to run `water_level_collector.py` as a background service.

   ### NSSM Setup Steps:
   - Extract the NSSM files and locate the `win64` directory:
     ```
     C:\Users\Lenovo T450s\Downloads\nssm-2.24-103-gdee49fc\nssm-2.24-103-gdee49fc\win64
     ```
   - Open CMD as Administrator and navigate to the directory:
     ```bash
     cd "C:\Users\Lenovo T450s\Downloads\nssm-2.24-103-gdee49fc\nssm-2.24-103-gdee49fc\win64"
     nssm install
     ```
   - In the NSSM installer:
     - **Application Path**:  
       `C:\Users\Lenovo T450s\AppData\Local\Programs\Python\Python313\python.exe`
     - **Startup Directory**:  
       `C:\Users\Lenovo T450s\PycharmProjects\old-lfews2`
     - **Arguments**:  
       `water_level_collector.py`
     - **Service Name**:  
       `WaterLevelCollector`

   - To manage the service:
     ```bash
     nssm start WaterLevelCollector    # Start the service
     nssm stop WaterLevelCollector     # Stop the service
     nssm remove WaterLevelCollector   # Remove the service
     ```

6. **Clone the Repository into Your IDE**
   - Use Git to clone the project:
     ```bash
     git clone https://github.com/your-org/old-lfews.git
     ```

7. **Run Migrations**
   - In your IDE terminal (e.g., PyCharm CE), run:
     ```bash
     python manage.py makemigrations
     python manage.py migrate
     ```

8. **Start the Django Server**
   - For development (accessible only on your device):
     ```bash
     python manage.py runserver
     ```
   - For access from other devices (on the same Wi-Fi/network):
     ```bash
     python manage.py runserver 0.0.0.0:8000
     ```
   - To get your IP address:
     - Open CMD and type:
       ```bash
       ipconfig
       ```
     - Look under **Wireless LAN adapter** → **IPv4 Address**.
     - Access the site from another device using the IP:
       ```
       http://<your-ip-address>:8000
       ```
       Example:
       ```
       http://192.168.41.1:8000
       ```

---

## Notes

- Ensure all devices (laptop, mobile phones, sensors) are connected to the same local network.
- Allow Python and Django through your firewall when prompted.
- If you experience issues connecting via IP, make sure your local firewall or antivirus isn’t blocking the port.

---
