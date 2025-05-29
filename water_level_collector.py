#!/usr/bin/env python
"""
Standalone script to continuously fetch water level data.
This script runs independently from the Django development server.
"""
import os
import sys
import time
import threading
import logging
from datetime import datetime

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lfews.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("water_level_collector.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("water_level_collector")

try:
    import django
    django.setup()
    
    # Import Django models after setting up Django
    from app.models import WaterLevelStation, WaterLevelData
    from pymodbus.client import ModbusTcpClient
    from pymodbus.exceptions import ModbusException
    
    logger.info("Django setup complete, models imported successfully")
except Exception as e:
    logger.error(f"Error during setup: {str(e)}")
    sys.exit(1)

def fetch_and_store_water_level_data():
    """
    Continuously fetch water level data from all active stations and store in database.
    This function runs in an infinite loop with error handling.
    """
    while True:
        try:
            # Get all active water level stations with their configurations
            active_stations = WaterLevelStation.objects.filter(status='active')
            
            # Get the current time for timestamping
            current_time = datetime.now()
            current_date = current_time.date()
            
            logger.info(f"Starting water level data collection cycle...")
            
            # Fetch data for each station and store in DB
            for station in active_stations:
                client = None
                try:
                    # Get the modbus configuration from the station object
                    modbus_ip = station.modbus_ip.strip()  # Remove any whitespace
                    modbus_port = int(station.modbus_port)
                    unit_id = int(station.unit_id)
                    register_address = int(station.register_address)
                    
                    logger.info(f"Processing {station.name} - IP: {modbus_ip}, Port: {modbus_port}, "
                          f"Unit: {unit_id}, Register: {register_address}")
                    
                    # Create Modbus client with configuration from database
                    client = ModbusTcpClient(
                        host=modbus_ip,
                        port=modbus_port,
                        timeout=2.0  # 2 second timeout for connection
                    )
                    
                    # Try to connect multiple times
                    for attempt in range(3):  # Try 3 times
                        try:
                            connection = client.connect()
                            if connection:
                                logger.info(f"Connected to {station.name} at {modbus_ip}:{modbus_port}")
                                
                                # Read holding register
                                response = client.read_holding_registers(
                                    address=register_address,
                                    count=1
                                )
                                
                                if response and hasattr(response, 'registers') and len(response.registers) > 0:
                                    # Get value from Modbus (this is in mm)
                                    level_value_mm = float(response.registers[0])
                                    logger.info(f"Raw reading from {station.name}: {level_value_mm}mm")
                                    
                                    # Only process if we have a valid reading
                                    if level_value_mm > 0:
                                        # Convert from mm to cm by dividing by 10
                                        level_value_cm = level_value_mm / 10.0
                                        
                                        try:
                                            # Create WaterLevelData record
                                            WaterLevelData.objects.create(
                                                station=station,
                                                data=level_value_cm,  # Store as cm
                                                date=current_date,
                                                time=current_time.time()
                                            )
                                            logger.info(f"Successfully stored water level data for {station.name}: {level_value_cm} cm")
                                            break  # Exit retry loop on success
                                        except Exception as db_error:
                                            logger.error(f"Database error for {station.name}: {str(db_error)}")
                                    else:
                                        logger.warning(f"Skipping invalid reading (0) for station {station.name}")
                                else:
                                    logger.warning(f"No valid data in response for {station.name}: {response if response else 'No response'}")
                            else:
                                logger.warning(f"Connection attempt {attempt + 1} failed for {station.name} at {modbus_ip}:{modbus_port}")
                                time.sleep(1)  # Wait 1 second between retries
                        except ModbusException as me:
                            logger.error(f"Modbus error on attempt {attempt + 1} for {station.name}: {str(me)}")
                            time.sleep(1)  # Wait 1 second between retries
                        except Exception as e:
                            logger.error(f"Error on attempt {attempt + 1} for {station.name}: {str(e)}")
                            time.sleep(1)  # Wait 1 second between retries
                        finally:
                            if client and not connection:
                                client.close()
                except Exception as e:
                    logger.error(f"Setup error for {station.name}: {str(e)}")
                finally:
                    # Always close the connection if it was created
                    if client:
                        try:
                            client.close()
                        except:
                            pass  # Ignore errors during close
            
            logger.info(f"Completed data collection cycle. Waiting 60 seconds before next cycle...")
            # Sleep for 60 seconds before next collection cycle
            time.sleep(60)
            
        except Exception as e:
            logger.error(f"Error in water level data thread: {str(e)}")
            time.sleep(60)  # On error, also wait 60 seconds before retry

if __name__ == "__main__":
    logger.info("Starting water level data collector script")
    
    try:
        # Run the main function directly (no threading needed since this is a standalone script)
        fetch_and_store_water_level_data()
    except KeyboardInterrupt:
        logger.info("Script terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)
