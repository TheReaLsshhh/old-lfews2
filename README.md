In order for this to work, here are few things to consider for this repository to work:

I am using Python`s Django framework.

1. Install XAMPP > Create database (old-lfews).
2. Install Python 3.13 (in my current date I made this Django project).
3. Install Modbus Poll application. In our case, the Modbus Poll application was provided by the organization by the time we made this project. Go to File > New > Connection > Connect, in Connection select
Modbus TCP/IP then enter the IP address of the sensors, or your preferred IP addresses.
4. Install PyCharm Community Edition or your prefered IDE for running Python projects.
5. Install NSSM (Non Sucking Service Manager) > Download the latest release. This app runs the water_level_collector.py in the Django folder project. For this to setup locate where you put the extracted
file and copy its path (C:\Users\Lenovo T450s\Downloads\nssm-2.24-103-gdee49fc\nssm-2.24-103-gdee49fc\win64) then open CMD as Administrator + cd C:\Users\Lenovo T450s\Downloads\nssm-2.24-103-gdee49fc\nssm-2.24-103-gdee49fc\win64 + 
nssm install + Application Path is to locate where your Python application is located (C:\Users\Lenovo T450s\AppData\Local\Programs\Python\Python313), then Startup Directory is where your Django project is located (C:\Users\Lenovo T450s\PycharmProjects\old-lfews2), then
Arguments is water_level_collector.py, lastly Service Name is WaterLevelCollector then Install Service. Start it by running (nssm start WaterLevelCollector), stop for (nssm stop WaterLevelCollector), and remove (nssm remove WaterLevelCollector).
6. Add the repository into your PyCharm Community Edition IDE using Git.
7. Apply python manage.py makemigrations and python manage.py migrate on your PyCharm CE terminal.
8. Run it by typing in your PyCharm CE terminal > python manage.py runserver (if you want only want your device for it to view) > python manage.py runserver 0.0.0.0:8000 (if you want mobile
and other desktop to view, run your CMD + ipconfig + look for Wireless LAN + IPv4 Address: actual ip address: just type the actual address on your Chrome/Edge/etc., for example is
192.168.41.1:8000, it should run locally with the same network/wifi connected).
