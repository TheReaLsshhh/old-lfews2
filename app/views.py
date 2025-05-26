from django.shortcuts import render, redirect   
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Logs, WaterLevelStation, WaterLevelData, WeatherStation, WeatherStatus, WeatherForecastStation, WeatherForecast
from django.http import JsonResponse, HttpResponse
from datetime import datetime, timedelta
import random
import requests
import threading
import time
from django.conf import settings
import pytz
from django.db.models import Q
from django.db import transaction
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import xlsxwriter
import json
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import base64
from django.template.loader import render_to_string
from io import BytesIO

# Add Modbus library import
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException, ConnectionException

# Create your views here.
def is_superuser(user):
    return user.is_superuser


def root_redirect(request):
    return redirect('admin_login')


def admin_login(request):
    if request.user.is_authenticated:
        return redirect('station_map')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_superuser:
            login(request, user)
            Logs.objects.create(user=user, action='login')
            return redirect('station_map')
        else:
            messages.error(request, 'Invalid credentials.')

    return render(request, 'admin_login.html')


@login_required
def admin_logout(request):
    # Log the logout activity
    if request.user.is_authenticated:
        Logs.objects.create(user=request.user, action='Logged out')
    
    # Perform logout
    logout(request)
    
    # Create a response that redirects to login page
    response = redirect('admin_login')
    
    # Add cache control headers to prevent back button from showing previous pages
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    return response

def register_sub_admin(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        position = request.POST.get('position')
        username = request.POST.get('username')
        password = request.POST.get('password')

        # Simple validation
        if not (full_name and position and username and password):
            messages.error(request, 'All fields are required.')
            return redirect('admin_login')

        # The PendingSubAdmin functionality appears to be incomplete
        # This section is commented out since the model doesn't exist
        '''
        # Prevent duplicate usernames
        if PendingSubAdmin.objects.filter(username=username).exists():
            messages.error(request, 'Username is already pending approval.')
            return redirect('admin_login')

        from .models import ApprovedSubAdmin
        if ApprovedSubAdmin.objects.filter(username=username).exists():
            messages.error(request, 'Username is already in use.')
            return redirect('admin_login')

        # Save to PendingSubAdmin
        PendingSubAdmin.objects.create(
            full_name=full_name,
            position=position,
            username=username,
            password=password  # hashing happens later on approval
        )
        '''
        
        messages.success(request, 'Sub-admin registration request submitted.')
        return redirect('admin_login')



def fetch_water_level(request):
    # Only get active stations
    stations = WaterLevelStation.objects.filter(status='active')
    response_data = {}
    
    # Get date range from request or default to yesterday-today
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date:
        start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    for station in stations:
        # Get live data
        station_data = WaterLevelData.objects.filter(
            station=station,
            date__gte=start_date,
            date__lte=end_date,
            type='live'  # Only include live data
        ).order_by('date', 'time')
        
        live_data_count = station_data.count()
        print(f"Found {live_data_count} live data points for {station.name}")
        
        # If no live data exists, create a fallback entry so the station shows up
        if live_data_count == 0:
            print(f"No live data found for station {station.name}. Creating a placeholder entry.")
            # Create a placeholder entry with a zero value but don't save it to the database
            current_time = datetime.now()
            placeholder = WaterLevelData(
                station=station,
                data=0,  # Zero value indicates no actual data yet
                date=current_time.date(),
                time=current_time.time(),
                type='placeholder'  # Mark as placeholder
            )
            # Instead of saving to DB, just create a queryset-like object with this placeholder
            station_data = [placeholder]
        
        # Prepare data for chart
        dates = []
        values = []
        data_types = []
        
        # Handle both querysets and lists (for placeholder data)
        for data_point in station_data:
            timestamp = f"{data_point.date.strftime('%Y-%m-%d')} {data_point.time.strftime('%H:%M:%S')}"
            dates.append(timestamp)
            values.append(data_point.data)
            data_types.append(data_point.type)
        
        # Debug info
        print(f"Station {station.name} response data:")
        print(f"  - Dates: {len(dates)} entries")
        print(f"  - Values: {len(values)} entries")
        print(f"  - Types: {data_types}")
        
        response_data[station.station_id] = {
            'name': station.name,
            'station_id': station.station_id,
            'dates': dates,
            'values': values,
            'green_threshold': station.green_threshold,
            'yellow_threshold': station.yellow_threshold,
            'orange_threshold': station.orange_threshold,
            'red_threshold': station.red_threshold,
            'latest_value': values[-1] if values else None,
            'has_live_data': any(data_type == 'live' for data_type in data_types) if data_types else False,
            'is_test_data': False,  # Always set to False since we're not using test data
            'data_types': data_types
        }
    
    return JsonResponse(response_data)


@login_required
def dashboard(request):
    # Station adding functionality removed - now only available in settings
    return render(request, 'dashboard.html')


@login_required
def weather_updates(request):
    """
    Render the weather updates page.
    """
    # Get all active weather stations
    weather_stations = WeatherStation.objects.filter(status='active')
    
    return render(request, 'weather_updates.html', {
        'weather_stations': weather_stations,
        'api_key': 'cb0c2dc0f7e84bdd8c2dc0f7e8ebdd4d'  # Your Wunderground API key
    })


# Global variable to track if the weather data fetching thread is running
weather_fetch_thread_running = False

# Function to fetch and store weather data periodically
def start_weather_data_thread():
    global weather_fetch_thread_running
    
    if weather_fetch_thread_running:
        return  # Thread already running
    
    weather_fetch_thread_running = True
    
    def fetch_and_store_weather_data():
        global weather_fetch_thread_running
        
        while weather_fetch_thread_running:
            try:
                # Get all active weather stations
                active_stations = WeatherStation.objects.filter(status='active')
                station_ids = [station.station_id for station in active_stations]
                
                # Fetch data for each station and store in DB
                for station_id in station_ids:
                    try:
                        # Fetch data from API
                        station_data = fetch_station_weather_data(station_id)
                        
                        if station_data and 'error' not in station_data:
                            # Get the station object
                            station = WeatherStation.objects.get(station_id=station_id)
                            
                            # Create WeatherStatus record
                            WeatherStatus.objects.create(
                                weather_station=station,
                                temperature=station_data.get('temperature', 'N/A'),
                                humidity=station_data.get('humidity', 'N/A'),
                                wind_speed=station_data.get('wind_speed', 'N/A'),
                                wind_direction=station_data.get('wind_direction', 'N/A'),
                                pressure=station_data.get('pressure', 'N/A'),
                                precipitation_rate=station_data.get('precipitation_rate', 'N/A'),
                                precipitation_total=station_data.get('precipitation_total', 'N/A'),
                                uv=station_data.get('uv', 'N/A'),
                                solar_radiation=station_data.get('solar_radiation', 'N/A')
                            )
                            print(f"Stored weather data for station {station_id}")
                    except Exception as e:
                        print(f"Error storing weather data for station {station_id}: {str(e)}")
                
                # Sleep for 5 minutes before fetching again
                time.sleep(300)  # 300 seconds = 5 minutes
                
            except Exception as e:
                print(f"Error in weather data thread: {str(e)}")
                time.sleep(60)  # On error, retry after 1 minute
    
    # Start the thread
    thread = threading.Thread(target=fetch_and_store_weather_data)
    thread.daemon = True  # Allow the thread to exit when the main program exits
    thread.start()
    print("Started weather data collection thread")


# Function to fetch weather data for a single station
def fetch_station_weather_data(station_id):
    try:
        # Get station details from database
        station = WeatherStation.objects.get(station_id=station_id, status='active')
        
        # API key for Wunderground
        api_key = 'cb0c2dc0f7e84bdd8c2dc0f7e8ebdd4d'
        
        # Build the API URL for current conditions
        current_url = f"https://api.weather.com/v2/pws/observations/current?stationId={station_id}&format=json&units=m&apiKey={api_key}"
        
        # Make the API request
        response = requests.get(current_url)
        
        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            
            # Log the raw API response to help with debugging
            print(f"Raw Weather API response for {station_id}:", data)
            
            # Extract the relevant weather data
            observation = data.get('observations', [{}])[0]
            
            # Format the timestamp properly using current time zone
            observation_time = 'N/A'
            try:
                # Get the observed time from API, with proper error handling
                obs_time_local = observation.get('obsTimeLocal')
                if obs_time_local:
                    # Convert API timestamp to proper format
                    current_year = datetime.now().year
                    
                    # Replace any future year with current year (fix for 2025 issue)
                    if '2025' in obs_time_local:
                        obs_time_local = obs_time_local.replace('2025', str(current_year))
                    
                    # Format in standard ISO format
                    observation_time = obs_time_local
            except Exception as e:
                print(f"Error formatting observation time: {str(e)}")
                # Use current time as fallback
                observation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Return the weather data
            return {
                'name': station.name,
                'station_id': station_id,
                'temperature': observation.get('metric', {}).get('temp', 'N/A'),
                'humidity': observation.get('humidity', 'N/A'),
                'wind_speed': observation.get('metric', {}).get('windSpeed', 'N/A'),
                'wind_direction': observation.get('winddir', 'N/A'),
                'pressure': observation.get('metric', {}).get('pressure', 'N/A'),
                'precipitation_rate': observation.get('metric', {}).get('precipRate', 'N/A'),
                'precipitation_total': observation.get('metric', {}).get('precipTotal', 'N/A'),
                'observation_time': observation_time,
                'uv': observation.get('uv', 'N/A'),
                'solar_radiation': observation.get('solarRadiation', 'N/A'),
            }
        else:
            return {
                'error': f"API Error: {response.status_code}",
                'error_details': response.text[:100]
            }
                
    except WeatherStation.DoesNotExist:
        return {'error': 'Station not found or inactive'}
    except Exception as e:
        return {'error': f"Exception: {str(e)}"}


@login_required
def fetch_weather_data(request):
    """
    Fetch weather data from Wunderground API for the requested stations.
    """
    # Get station IDs from request or use all active stations
    station_ids = request.GET.getlist('station_ids[]', [])
    
    if not station_ids:
        # If no stations specified, get all active stations
        active_stations = WeatherStation.objects.filter(status='active')
        station_ids = [station.station_id for station in active_stations]
    
    # Prepare response data
    weather_data = {}
    
    # Fetch data for each station
    for station_id in station_ids:
        try:
            # Get station details from database
            station = WeatherStation.objects.get(station_id=station_id, status='active')
            
            # Fetch current weather data
            station_data = fetch_station_weather_data(station_id)
            
            if 'error' not in station_data:
                # Get recent logs/history for this station (last 5 records)
                recent_logs = WeatherStatus.objects.filter(
                    weather_station=station
                ).order_by('-timestamp')[:5]
                
                # Get server's timezone information
                timezone_name = getattr(settings, 'TIME_ZONE', 'UTC')
                server_timezone = pytz.timezone(timezone_name)
                current_time = datetime.now(server_timezone)
                timezone_offset = current_time.strftime('%z')
                
                # Add timezone info to the response
                station_data['timezone_info'] = {
                    'name': timezone_name,
                    'offset': timezone_offset
                }
                
                # Add logs to the response with timezone info
                station_data['logs'] = [{
                    'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S %z'),  # Include timezone offset
                    'temperature': log.temperature,
                    'humidity': log.humidity,
                    'wind_speed': log.wind_speed,
                    'precipitation_total': log.precipitation_total
                } for log in recent_logs]
                
                # Add to response
                weather_data[station_id] = station_data
            else:
                # Return error information
                weather_data[station_id] = {
                    'name': station.name,
                    'station_id': station_id,
                    'error': station_data['error'],
                    'error_details': station_data.get('error_details', '')
                }
                
        except WeatherStation.DoesNotExist:
            # If the station doesn't exist or is inactive
            weather_data[station_id] = {
                'station_id': station_id,
                'error': 'Station not found or inactive'
            }
        except Exception as e:
            # Handle any other exceptions
            weather_data[station_id] = {
                'station_id': station_id,
                'error': f"Exception: {str(e)}"
            }
    
    # Return the weather data as JSON
    return JsonResponse(weather_data)


# Start the weather data thread when the server starts
def start_weather_thread_on_server_start():
    threading.Timer(5, start_weather_data_thread).start()

# Call the function to start the thread when the module is loaded
start_weather_thread_on_server_start()


@login_required
def settings_view(request):
    # Initialize active_tab variable
    active_tab = request.POST.get('active_tab', 'water-level-tab')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Water level station actions
        if action == 'add_station':
            with transaction.atomic():
                # Get form data
                name = request.POST.get('name')
                station_id = request.POST.get('station_id')
                green = float(request.POST.get('green_threshold'))
                yellow = float(request.POST.get('yellow_threshold'))
                orange = float(request.POST.get('orange_threshold'))
                red = float(request.POST.get('red_threshold'))
                modbus_ip = request.POST.get('modbus-ip')
                modbus_port = int(request.POST.get('modbus-port'))
                unit_id = int(request.POST.get('unit-id'))
                register_address = int(request.POST.get('register-address'))
                latitude = request.POST.get('latitude')
                longitude = request.POST.get('longitude')
                
                # Create new station
                station = WaterLevelStation.objects.create(
                    name=name,
                    station_id=station_id,
                    green_threshold=green,
                    yellow_threshold=yellow,
                    orange_threshold=orange,
                    red_threshold=red,
                    modbus_ip=modbus_ip,
                    modbus_port=modbus_port,
                    unit_id=unit_id,
                    register_address=register_address,
                    latitude=latitude if latitude else None,
                    longitude=longitude if longitude else None
                )
                
                # Log the activity
                Logs.objects.create(
                    user=request.user,
                    action=f"Added water level station: {name} ({station_id}) with thresholds G:{green}cm, Y:{yellow}cm, O:{orange}cm, R:{red}cm"
                )
                
                messages.success(request, 'Station added successfully.')
            
        elif action == 'edit_station':
            with transaction.atomic():
                # Get form data
                station_id = request.POST.get('station_id')  # This matches the hidden field name in the form
                name = request.POST.get('name')
                station_identifier = request.POST.get('station_identifier')
                green = float(request.POST.get('green_threshold'))
                yellow = float(request.POST.get('yellow_threshold'))
                orange = float(request.POST.get('orange_threshold'))
                red = float(request.POST.get('red_threshold'))
                modbus_ip = request.POST.get('modbus-ip')
                modbus_port = int(request.POST.get('modbus-port'))
                unit_id = int(request.POST.get('unit-id'))
                register_address = int(request.POST.get('register-address'))
                latitude = request.POST.get('latitude')
                longitude = request.POST.get('longitude')
                
                # Get the station object
                try:
                    station = WaterLevelStation.objects.get(id=station_id)
                    
                    # Update the fields
                    old_name = station.name
                    old_station_id = station.station_id
                    
                    station.name = name
                    station.station_id = station_identifier
                    station.green_threshold = green
                    station.yellow_threshold = yellow
                    station.orange_threshold = orange
                    station.red_threshold = red
                    station.modbus_ip = modbus_ip
                    station.modbus_port = modbus_port
                    station.unit_id = unit_id
                    station.register_address = register_address
                    station.latitude = latitude if latitude else None
                    station.longitude = longitude if longitude else None
                    
                    # Save the changes
                    station.save()
                    
                    # Log the activity
                    Logs.objects.create(
                        user=request.user,
                        action=f"Edited water level station: {name} ({station_identifier}), was {old_name} ({old_station_id})"
                    )
                    
                    messages.success(request, 'Station updated successfully.')
                    
                except WaterLevelStation.DoesNotExist:
                    messages.error(request, 'Station not found.')
                
            active_tab = 'water-level-tab'
                
        elif action == 'toggle_status':
            with transaction.atomic():
                # Get the station
                station_id = request.POST.get('station_id')
                
                try:
                    station = WaterLevelStation.objects.get(id=station_id)
                    
                    # Toggle the status
                    old_status = station.status
                    if station.status == 'active':
                        station.status = 'inactive'
                        status_message = 'disabled'
                        action_type = 'Disabled'
                    else:
                        station.status = 'active'
                        status_message = 'enabled'
                        action_type = 'Enabled'
                    
                    # Save the changes
                    station.save()
                    
                    # Log the activity
                    Logs.objects.create(
                        user=request.user,
                        action=f"{action_type} water level station: {station.name} ({station.station_id})"
                    )
                    
                    messages.success(request, f'Station {station.name} {status_message} successfully.')
                    
                except WaterLevelStation.DoesNotExist:
                    messages.error(request, 'Station not found.')
                
            active_tab = 'water-level-tab'
                
        elif action == 'delete_station':
            with transaction.atomic():
                # Get the station
                station_id = request.POST.get('station_id')
                
                try:
                    station = WaterLevelStation.objects.get(id=station_id)
                    station_name = station.name
                    station_identifier = station.station_id
                    
                    # Log the activity before deletion
                    Logs.objects.create(
                        user=request.user,
                        action=f"Deleted water level station: {station_name} ({station_identifier})"
                    )
                    
                    # Delete the station
                    station.delete()
                    
                    messages.success(request, f'Station {station_name} deleted successfully.')
                    
                except WaterLevelStation.DoesNotExist:
                    messages.error(request, 'Station not found.')
                
            active_tab = 'water-level-tab'
                
        # Weather station actions
        elif action == 'add_weather_station':
            with transaction.atomic():
                # Get form data
                name = request.POST.get('name')
                station_id = request.POST.get('station_id')
                latitude = request.POST.get('latitude')
                longitude = request.POST.get('longitude')
                
                # Create new weather station
                station = WeatherStation.objects.create(
                    name=name,
                    station_id=station_id,
                    latitude=latitude if latitude else None,
                    longitude=longitude if longitude else None
                )
                
                # Log the activity
                Logs.objects.create(
                    user=request.user,
                    action=f"Added weather station: {name} ({station_id})"
                )
                
                messages.success(request, 'Weather station added successfully.')
            
        elif action == 'edit_weather_station':
            with transaction.atomic():
                # Get form data
                station_id = request.POST.get('station_id')  # This is the primary key ID
                name = request.POST.get('name')
                
                # Try to get the station identifier from different possible field names
                station_identifier = request.POST.get('station_identifier')
                if not station_identifier:
                    station_identifier = request.POST.get('station_id')  # Fallback
                
                latitude = request.POST.get('latitude')
                longitude = request.POST.get('longitude')
                
                # Get the station object
                try:
                    station = WeatherStation.objects.get(id=station_id)
                    
                    # Update the fields
                    old_name = station.name
                    old_station_id = station.station_id
                    
                    station.name = name
                    station.station_id = station_identifier
                    station.latitude = latitude if latitude else None
                    station.longitude = longitude if longitude else None
                    
                    # Save the changes
                    station.save()
                    
                    # Log the activity
                    Logs.objects.create(
                        user=request.user,
                        action=f"Edited weather station: {name} ({station_identifier}), was {old_name} ({old_station_id})"
                    )
                    
                    messages.success(request, 'Weather station updated successfully.')
                    
                except WeatherStation.DoesNotExist:
                    messages.error(request, 'Weather station not found.')
                
            active_tab = 'weather-tab'
                
        elif action == 'toggle_weather_status':
            with transaction.atomic():
                # Get the station
                station_id = request.POST.get('station_id')
                
                try:
                    station = WeatherStation.objects.get(id=station_id)
                    
                    # Toggle the status
                    old_status = station.status
                    if station.status == 'active':
                        station.status = 'inactive'
                        status_message = 'disabled'
                        action_type = 'Disabled'
                    else:
                        station.status = 'active'
                        status_message = 'enabled'
                        action_type = 'Enabled'
                    
                    # Save the changes
                    station.save()
                    
                    # Log the activity
                    Logs.objects.create(
                        user=request.user,
                        action=f"{action_type} weather station: {station.name} ({station.station_id})"
                    )
                    
                    messages.success(request, f'Weather station {station.name} {status_message} successfully.')
                    
                except WeatherStation.DoesNotExist:
                    messages.error(request, 'Weather station not found.')
                
            active_tab = 'weather-tab'
                
        elif action == 'delete_weather_station':
            with transaction.atomic():
                # Get the station
                station_id = request.POST.get('station_id')
                
                try:
                    station = WeatherStation.objects.get(id=station_id)
                    station_name = station.name
                    station_identifier = station.station_id
                    
                    # Log the activity before deletion
                    Logs.objects.create(
                        user=request.user,
                        action=f"Deleted weather station: {station_name} ({station_identifier})"
                    )
                    
                    # Delete the station
                    station.delete()
                    
                    messages.success(request, f'Weather station {station_name} deleted successfully.')
                    
                except WeatherStation.DoesNotExist:
                    messages.error(request, 'Weather station not found.')
                
            active_tab = 'weather-tab'
                
        # Weather forecast station actions
        elif action == 'add_forecast_station':
            with transaction.atomic():
                # Get form data
                name = request.POST.get('name')
                location = request.POST.get('location')
                latitude = float(request.POST.get('latitude'))
                longitude = float(request.POST.get('longitude'))
                
                # Create new forecast station
                station = WeatherForecastStation.objects.create(
                    name=name,
                    location=location,
                    latitude=latitude,
                    longitude=longitude
                )
                
                # Log the activity
                Logs.objects.create(
                    user=request.user,
                    action=f"Added forecast station: {name} ({location}) at lat:{latitude}, lon:{longitude}"
                )
                
                messages.success(request, 'Weather forecast station added successfully.')
            
        elif action == 'edit_forecast_station':
            with transaction.atomic():
                # Get form data
                station_id = request.POST.get('station_id')  # This is the primary key ID
                name = request.POST.get('name')
                location = request.POST.get('location')
                latitude = float(request.POST.get('latitude'))
                longitude = float(request.POST.get('longitude'))
                
                # Get the station object
                try:
                    station = WeatherForecastStation.objects.get(id=station_id)
                    
                    # Update the fields
                    old_name = station.name
                    old_location = station.location
                    
                    station.name = name
                    station.location = location
                    station.latitude = latitude
                    station.longitude = longitude
                    
                    # Save the changes
                    station.save()
                    
                    # Log the activity
                    Logs.objects.create(
                        user=request.user,
                        action=f"Edited forecast station: {name} ({location}), was {old_name} ({old_location})"
                    )
                    
                    messages.success(request, 'Weather forecast station updated successfully.')
                    
                except WeatherForecastStation.DoesNotExist:
                    messages.error(request, 'Weather forecast station not found.')
                
            active_tab = 'forecast-tab'
                
        elif action == 'toggle_forecast_status':
            with transaction.atomic():
                # Get the station
                station_id = request.POST.get('station_id')
                
                try:
                    station = WeatherForecastStation.objects.get(id=station_id)
                    
                    # Toggle the status
                    old_status = station.status
                    if station.status == 'active':
                        station.status = 'inactive'
                        status_message = 'disabled'
                        action_type = 'Disabled'
                    else:
                        station.status = 'active'
                        status_message = 'enabled'
                        action_type = 'Enabled'
                    
                    # Save the changes
                    station.save()
                    
                    # Log the activity
                    Logs.objects.create(
                        user=request.user,
                        action=f"{action_type} forecast station: {station.name} ({station.location})"
                    )
                    
                    messages.success(request, f'Weather forecast station {station.name} {status_message} successfully.')
                    
                except WeatherForecastStation.DoesNotExist:
                    messages.error(request, 'Weather forecast station not found.')
                
            active_tab = 'forecast-tab'
                
        elif action == 'delete_forecast_station':
            with transaction.atomic():
                # Get the station
                station_id = request.POST.get('station_id')
                
                try:
                    station = WeatherForecastStation.objects.get(id=station_id)
                    station_name = station.name
                    location = station.location
                    
                    # Log the activity before deletion
                    Logs.objects.create(
                        user=request.user,
                        action=f"Deleted forecast station: {station_name} ({location})"
                    )
                    
                    # Delete the station
                    station.delete()
                    
                    messages.success(request, f'Weather forecast station {station_name} deleted successfully.')
                    
                except WeatherForecastStation.DoesNotExist:
                    messages.error(request, 'Weather forecast station not found.')
                
            active_tab = 'forecast-tab'
    
    # Get all stations for display in the template
    stations = WaterLevelStation.objects.all().order_by('-date_created')
    weather_stations = WeatherStation.objects.all().order_by('-date_added')
    forecast_stations = WeatherForecastStation.objects.all().order_by('-date_added')
    
    # Get active tab from query parameter or use the one set during form processing
    tab_param = request.GET.get('tab')
    if tab_param:
        active_tab = tab_param
    
    # Log the view access
    Logs.objects.create(
        user=request.user,
        action="Viewed settings page"
    )
    
    context = {
        'stations': stations,
        'weather_stations': weather_stations,
        'forecast_stations': forecast_stations,
        'active_tab': active_tab
    }
    
    return render(request, 'settings.html', context)


@login_required
def weather_forecast(request):
    """
    Render the weather forecast page.
    """
    # Get all active forecast stations
    forecast_stations = WeatherForecastStation.objects.filter(status='active')
    
    return render(request, 'weather_forecast.html', {
        'forecast_stations': forecast_stations
    })

@login_required
def fetch_forecast_data(request):
    """
    Fetch forecast data from Open-Meteo API for the requested stations or locations.
    """
    # Get station IDs from request or use all active stations
    station_ids = request.GET.getlist('station_ids[]', [])
    
    if not station_ids:
        # If no stations specified, get all active stations
        active_stations = WeatherForecastStation.objects.filter(status='active')
        station_ids = [str(station.id) for station in active_stations]
    
    # Prepare response data
    forecast_data = {}
    
    # Fetch data for each station
    for station_id in station_ids:
        try:
            # Get station details from database
            station = WeatherForecastStation.objects.get(id=station_id, status='active')
            
            # Fetch forecast data from Open-Meteo API
            station_data = fetch_station_forecast_data(station)
            
            # Add to response
            forecast_data[station_id] = station_data
                
        except WeatherForecastStation.DoesNotExist:
            # If the station doesn't exist or is inactive
            forecast_data[station_id] = {
                'station_id': station_id,
                'error': 'Station not found or inactive'
            }
        except Exception as e:
            # Handle any other exceptions
            forecast_data[station_id] = {
                'station_id': station_id,
                'error': f"Exception: {str(e)}"
            }
    
    # Return the forecast data as JSON
    return JsonResponse(forecast_data)

def fetch_station_forecast_data(station):
    """
    Fetch and process forecast data for a specific station using Open-Meteo API.
    """
    try:
        # Build the API URL for forecast
        base_url = "https://api.open-meteo.com/v1/forecast"
        
        # Form parameters for the API request
        params = {
            'latitude': station.latitude,
            'longitude': station.longitude,
            'hourly': 'temperature_2m,precipitation_probability,dew_point_2m,relative_humidity_2m',
            'timezone': 'auto'
        }
        
        # Make the API request
        response = requests.get(base_url, params=params)
        
        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            
            # Extract the forecast data
            hourly_data = data.get('hourly', {})
            timezone = data.get('timezone', 'UTC')
            
            # Get the time data
            times = hourly_data.get('time', [])
            temperatures = hourly_data.get('temperature_2m', [])
            precipitation_probs = hourly_data.get('precipitation_probability', [])
            dew_points = hourly_data.get('dew_point_2m', [])
            humidities = hourly_data.get('relative_humidity_2m', [])
            
            # Process and organize the forecast data
            forecast_data = []
            
            for i in range(len(times)):
                if i < len(temperatures) and i < len(precipitation_probs) and i < len(dew_points) and i < len(humidities):
                    forecast_time = times[i]
                    forecast_data.append({
                        'time': forecast_time,
                        'temperature': temperatures[i],
                        'precipitation_probability': precipitation_probs[i],
                        'dew_point': dew_points[i],
                        'humidity': humidities[i]
                    })
            
            # Save the forecast data to the database
            save_forecast_data(station, forecast_data)
            
            # Create the response
            days_forecast = process_forecast_by_day(forecast_data)
            
            return {
                'name': station.name,
                'location': station.location,
                'latitude': station.latitude,
                'longitude': station.longitude,
                'days': days_forecast,
                'timezone': timezone,
                'update_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            return {
                'error': f"API Error: {response.status_code}",
                'error_details': response.text[:100]
            }
                
    except Exception as e:
        return {'error': f"Exception: {str(e)}"}

def process_forecast_by_day(forecast_data):
    """
    Process hourly forecast data into daily groups.
    """
    days_forecast = {}
    
    for entry in forecast_data:
        # Get date from datetime string
        date_str = entry['time'].split('T')[0]
        
        # Initialize the day entry if it doesn't exist
        if date_str not in days_forecast:
            days_forecast[date_str] = {
                'date': date_str,
                'hourly': [],
                'min_temp': float('inf'),
                'max_temp': float('-inf'),
                'avg_precipitation_probability': 0,
                'hours_count': 0
            }
        
        # Convert 24-hour time to 12-hour time with AM/PM
        time_24h = entry['time'].split('T')[1]
        try:
            # Parse the time part
            hour, minute = time_24h.split(':')[:2]
            hour = int(hour)
            
            # Determine AM/PM
            if hour == 0:
                time_12h = f"12:{minute} AM"
            elif hour < 12:
                time_12h = f"{hour}:{minute} AM"
            elif hour == 12:
                time_12h = f"12:{minute} PM"
            else:
                time_12h = f"{hour-12}:{minute} PM"
        except Exception as e:
            print(f"Error converting time format: {str(e)}")
            time_12h = time_24h  # Fallback to original format if conversion fails
        
        # Add hourly data
        hour_data = {
            'time': time_12h,
            'temperature': entry['temperature'],
            'precipitation_probability': entry['precipitation_probability'],
            'dew_point': entry['dew_point'],
            'humidity': entry['humidity']
        }
        days_forecast[date_str]['hourly'].append(hour_data)
        
        # Update day statistics
        days_forecast[date_str]['min_temp'] = min(days_forecast[date_str]['min_temp'], entry['temperature'])
        days_forecast[date_str]['max_temp'] = max(days_forecast[date_str]['max_temp'], entry['temperature'])
        days_forecast[date_str]['avg_precipitation_probability'] += entry['precipitation_probability']
        days_forecast[date_str]['hours_count'] += 1
    
    # Calculate averages and format
    for date_str, day_data in days_forecast.items():
        if day_data['hours_count'] > 0:
            day_data['avg_precipitation_probability'] /= day_data['hours_count']
        
        # Determine day weather icon
        day_data['icon'] = determine_day_weather_icon(day_data)
    
    # Convert to list sorted by date
    return [days_forecast[date] for date in sorted(days_forecast.keys())]

def determine_day_weather_icon(day_data):
    """
    Determine the appropriate weather icon based on forecast data.
    """
    avg_precip = day_data['avg_precipitation_probability']
    max_temp = day_data['max_temp']
    
    if avg_precip >= 70:
        return 'fa-cloud-showers-heavy'  # Heavy rain
    elif avg_precip >= 40:
        return 'fa-cloud-rain'  # Rain
    elif avg_precip >= 20:
        return 'fa-cloud-sun-rain'  # Light rain
    elif max_temp >= 30:
        return 'fa-sun'  # Hot and sunny
    elif max_temp <= 5:
        return 'fa-snowflake'  # Cold
    else:
        return 'fa-cloud-sun'  # Partly cloudy

def save_forecast_data(station, forecast_data):
    """
    Save or update forecast data in the database.
    """
    # Clear previous forecasts for this station
    current_time = datetime.now()
    WeatherForecast.objects.filter(forecast_station=station, fetch_time__lt=current_time - timedelta(hours=6)).delete()
    
    # Check if we already have recent forecasts
    if WeatherForecast.objects.filter(forecast_station=station, fetch_time__gt=current_time - timedelta(hours=6)).exists():
        # Skip saving if we have recent data
        return
    
    # Save new forecast entries
    for entry in forecast_data:
        try:
            forecast_time = datetime.fromisoformat(entry['time'].replace('Z', '+00:00'))
            
            # Create forecast record
            WeatherForecast.objects.create(
                forecast_station=station,
                timestamp=forecast_time,
                temperature=entry['temperature'],
                precipitation_probability=entry['precipitation_probability'],
                relative_humidity=entry['humidity'],
                dew_point=entry['dew_point']
            )
        except Exception as e:
            print(f"Error saving forecast entry: {str(e)}")

# Start forecast data background refresh
def start_forecast_data_thread():
    thread = threading.Thread(target=refresh_forecast_data_periodically)
    thread.daemon = True
    thread.start()
    print("Started weather forecast data refresh thread")

def refresh_forecast_data_periodically():
    """
    Periodically refresh forecast data for all active stations.
    """
    while True:
        try:
            # Get all active forecast stations
            active_stations = WeatherForecastStation.objects.filter(status='active')
            
            # Fetch forecast for each station
            for station in active_stations:
                try:
                    fetch_station_forecast_data(station)
                    print(f"Refreshed forecast data for {station.name}")
                except Exception as e:
                    print(f"Error refreshing forecast for {station.name}: {str(e)}")
            
            # Sleep for 3 hours before refreshing again
            # API data is typically updated every 3-6 hours
            time.sleep(3 * 60 * 60)  # 3 hours in seconds
            
        except Exception as e:
            print(f"Error in forecast refresh thread: {str(e)}")
            time.sleep(30 * 60)  # On error, retry after 30 minutes

# Start the forecast refresh thread when the server starts
def start_forecast_thread_on_server_start():
    threading.Timer(10, start_forecast_data_thread).start()

# Call the function to start the thread when the module is loaded
start_forecast_thread_on_server_start()

# Global variable to track if the water level data fetching thread is running
water_level_fetch_thread_running = False

# Function to fetch and store water level data from modbus sensors periodically
def start_water_level_thread():
    global water_level_fetch_thread_running
    
    if water_level_fetch_thread_running:
        return  # Thread already running
    
    water_level_fetch_thread_running = True
    
    def fetch_and_store_water_level_data():
        global water_level_fetch_thread_running
        
        while water_level_fetch_thread_running:
            try:
                # Get all active water level stations with their configurations
                active_stations = WaterLevelStation.objects.filter(status='active')
                
                # Get the current time for timestamping
                current_time = datetime.now()
                current_date = current_time.date()
                
                print(f"\n[{current_time}] Starting water level data collection cycle...")
                
                # Fetch data for each station and store in DB
                for station in active_stations:
                    client = None
                    try:
                        # Get the modbus configuration from the station object
                        modbus_ip = station.modbus_ip.strip()  # Remove any whitespace
                        modbus_port = int(station.modbus_port)
                        unit_id = int(station.unit_id)
                        register_address = int(station.register_address)
                        
                        print(f"[{current_time}] Processing {station.name} - IP: {modbus_ip}, Port: {modbus_port}, "
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
                                    print(f"[{current_time}] Connected to {station.name} at {modbus_ip}:{modbus_port}")
                                    
                                    # Read holding register
                                    response = client.read_holding_registers(
                                        address=register_address,
                                        count=1
                                    )
                                    
                                    if response and hasattr(response, 'registers') and len(response.registers) > 0:
                                        # Get value from Modbus (this is in mm)
                                        level_value_mm = float(response.registers[0])
                                        print(f"[{current_time}] Raw reading from {station.name}: {level_value_mm}mm")
                                        
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
                                                    time=current_time.time(),
                                                    type='live'  # Mark as live data
                                                )
                                                print(f"[{current_time}] Successfully stored water level data for {station.name}: {level_value_cm} cm")
                                                break  # Exit retry loop on success
                                            except Exception as db_error:
                                                print(f"[{current_time}] Database error for {station.name}: {str(db_error)}")
                                        else:
                                            print(f"[{current_time}] Skipping invalid reading (0) for station {station.name}")
                                    else:
                                        print(f"[{current_time}] No valid data in response for {station.name}: {response if response else 'No response'}")
                                else:
                                    print(f"[{current_time}] Connection attempt {attempt + 1} failed for {station.name} at {modbus_ip}:{modbus_port}")
                                    time.sleep(1)  # Wait 1 second between retries
                            except ModbusException as me:
                                print(f"[{current_time}] Modbus error on attempt {attempt + 1} for {station.name}: {str(me)}")
                                time.sleep(1)  # Wait 1 second between retries
                            except Exception as e:
                                print(f"[{current_time}] Error on attempt {attempt + 1} for {station.name}: {str(e)}")
                                time.sleep(1)  # Wait 1 second between retries
                            finally:
                                if client and not connection:
                                    client.close()
                    except Exception as e:
                        print(f"[{current_time}] Setup error for {station.name} ({modbus_ip}:{modbus_port}): {str(e)}")
                    finally:
                        # Always close the connection if it was created
                        if client:
                            try:
                                client.close()
                            except:
                                pass  # Ignore errors during close
                
                print(f"[{current_time}] Completed data collection cycle. Waiting 60 seconds before next cycle...")
                # Sleep for 60 seconds before next collection cycle
                time.sleep(60)  # Check every 60 seconds for new data
                
            except Exception as e:
                print(f"[{datetime.now()}] Error in water level data thread: {str(e)}")
                time.sleep(60)  # On error, also wait 60 seconds before retry
    
    # Start the thread
    thread = threading.Thread(target=fetch_and_store_water_level_data)
    thread.daemon = True  # Allow the thread to exit when the main program exits
    thread.start()
    print("Started water level data collection thread")

# Start the water level data thread when the server starts
def start_water_level_thread_on_server_start():
    threading.Timer(5, start_water_level_thread).start()

# Call the function to start the thread when the module is loaded
start_water_level_thread_on_server_start()

@login_required
def activity_logs(request):
    # Get filter parameters from query string
    log_type = request.GET.get('log_type', '')
    search_query = request.GET.get('search', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Start with all logs
    logs = Logs.objects.all()
    
    # Apply filters for different station types
    if log_type == 'water_level':
        logs = logs.filter(action__icontains='water level station')
    elif log_type == 'weather':
        logs = logs.filter(action__icontains='weather station')
    elif log_type == 'forecast':
        logs = logs.filter(action__icontains='forecast station')
    
    # Apply action type filters
    action_type = request.GET.get('action_type', '')
    if action_type == 'add':
        logs = logs.filter(action__istartswith='Added')
    elif action_type == 'edit':
        logs = logs.filter(action__istartswith='Edited')
    elif action_type == 'delete':
        logs = logs.filter(action__istartswith='Deleted')
    elif action_type == 'enable':
        logs = logs.filter(action__istartswith='Enabled')
    elif action_type == 'disable':
        logs = logs.filter(action__istartswith='Disabled')
    
    # Apply search filter
    if search_query:
        logs = logs.filter(
            Q(action__icontains=search_query) | 
            Q(user__username__icontains=search_query)
        )
    
    # Apply date filters
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            logs = logs.filter(timestamp__date__gte=date_from)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            logs = logs.filter(timestamp__date__lte=date_to)
        except ValueError:
            pass
    
    # Only show station management logs by filtering for specific actions
    station_management_terms = [
        'station:', 'added', 'edited', 'deleted', 'enabled', 'disabled'
    ]
    query = Q()
    for term in station_management_terms:
        query |= Q(action__icontains=term)
    logs = logs.filter(query)
    
    # Order by timestamp descending (newest first)
    logs = logs.order_by('-timestamp')
    
    return render(request, 'activity_logs.html', {
        'logs': logs,
        'log_type': log_type,
        'action_type': action_type,
        'search_query': search_query,
        'date_from': date_from,
        'date_to': date_to,
    })

@login_required
def generate_report(request):
    if request.method != 'POST':
        messages.error(request, 'Invalid request method')
        return redirect('settings')
        
    report_type = request.POST.get('report_type')
    date_from = request.POST.get('date_from')
    date_to = request.POST.get('date_to')
    format_type = request.POST.get('format')
    
    try:
        date_from = datetime.strptime(date_from, '%Y-%m-%d')
        date_to = datetime.strptime(date_to, '%Y-%m-%d')
        date_to = date_to + timedelta(days=1)  # Include the entire end date
    except ValueError:
        messages.error(request, 'Invalid date format')
        return redirect('settings')
        
    if report_type == 'water_level':
        include_readings = request.POST.get('include_readings') == '1'
        include_alerts = request.POST.get('include_alerts') == '1'
        include_charts = request.POST.get('include_charts') == '1'
        station_id = request.POST.get('station_id')
        
        # For chart reports, we need a specific station
        if format_type == 'chart' and station_id == 'all':
            messages.error(request, 'Please select a specific station for chart reports')
            return redirect('settings')
        
        # Prepare data for report
        report_data = []
        
        # Add header row (add Latitude and Longitude)
        headers = ['Station Name', 'Station ID', 'Latitude', 'Longitude', 'Status', 'Date', 'Time', 'Water Level (cm)', 'Alert Status']
        report_data.append(headers)
        
        # Add data rows with station grouping
        current_station = None
        station_data = []
        
        # For chart type, we only need one specific station
        if format_type == 'chart':
            try:
                station = WaterLevelStation.objects.get(id=station_id)
                stations = [station]
            except WaterLevelStation.DoesNotExist:
                messages.error(request, 'Selected station not found')
                return redirect('settings')
        else:
            # Get all water level stations or filter by station_id
            if station_id != 'all':
                try:
                    station = WaterLevelStation.objects.get(id=station_id)
                    stations = [station]
                except WaterLevelStation.DoesNotExist:
                    messages.error(request, 'Selected station not found')
                    return redirect('settings')
            else:
                # Only include active stations when "All Active Water Stations" is selected
                stations = WaterLevelStation.objects.filter(status='active')
        
        for station in stations:
            # Get all readings for the date range
            readings = WaterLevelData.objects.filter(
                station=station,
                date__range=(date_from.date(), date_to.date())
            ).order_by('date', 'time')
            
            if readings.exists():
                for reading in readings:
                    row = [
                        station.name,
                        station.station_id,
                        station.latitude if station.latitude is not None else 'N/A',
                        station.longitude if station.longitude is not None else 'N/A',
                        station.status,
                        reading.date.strftime('%Y-%m-%d'),
                        reading.time.strftime('%H:%M:%S'),
                        f"{reading.data:.2f}",
                    ]
                    
                    # Get the alert status based on thresholds
                    alert_status = 'Normal'
                    level = reading.data
                    if level >= station.red_threshold:
                        alert_status = 'Critical (Red)'
                    elif level >= station.orange_threshold:
                        alert_status = 'High (Orange)'
                    elif level >= station.yellow_threshold:
                        alert_status = 'Medium (Yellow)'
                    elif level >= station.green_threshold:
                        alert_status = 'Low (Green)'
                    
                    row.append(alert_status)
                    station_data.append({'row': row, 'alert': alert_status, 'station': station.name, 'reading': reading})
            else:
                # Add a row even if no readings
                row = [
                    station.name,
                    station.station_id,
                    station.latitude if station.latitude is not None else 'N/A',
                    station.longitude if station.longitude is not None else 'N/A',
                    station.status,
                    'N/A', 
                    'N/A', 
                    'N/A', 
                    'N/A'
                ]
                station_data.append({'row': row, 'alert': 'N/A', 'station': station.name, 'reading': None})
        
        # Add all rows to report data
        for data in station_data:
            report_data.append(data['row'])
    
    elif report_type == 'weather':
        include_temp = request.POST.get('include_temperature') == '1'
        include_humidity = request.POST.get('include_humidity') == '1'
        include_wind = request.POST.get('include_wind') == '1'
        include_precip = request.POST.get('include_precipitation') == '1'
        
        # Get all active weather stations
        stations = WeatherStation.objects.filter(status='active')
        
        # Prepare data for report
        report_data = []
        
        # Add header row (add Latitude and Longitude)
        headers = ['Station Name', 'Station ID', 'Latitude', 'Longitude', 'Status', 'Date', 'Time']
        if include_temp:
            headers.append('Temperature (°C)')
        if include_humidity:
            headers.append('Humidity (%)')
        if include_wind:
            headers.extend(['Wind Speed (km/h)', 'Wind Direction'])
        if include_precip:
            headers.extend(['Precipitation Rate (mm/h)', 'Total Precipitation (mm)'])
        report_data.append(headers)
        
        # For station grouping
        station_data = []
        
        # Add data rows
        for station in stations:
            # Get all weather status records for the date range
            weather_records = WeatherStatus.objects.filter(
                weather_station=station,
                timestamp__range=(date_from, date_to)
            ).order_by('timestamp')
            
            if weather_records.exists():
                for record in weather_records:
                    row = [
                        station.name,
                        station.station_id,
                        station.latitude if station.latitude is not None else 'N/A',
                        station.longitude if station.longitude is not None else 'N/A',
                        station.status,
                        record.timestamp.strftime('%Y-%m-%d'),
                        record.timestamp.strftime('%H:%M:%S')
                    ]
                    
                    if include_temp:
                        row.append(record.temperature if record.temperature else 'N/A')
                    if include_humidity:
                        row.append(record.humidity if record.humidity else 'N/A')
                    if include_wind:
                        row.extend([
                            record.wind_speed if record.wind_speed else 'N/A',
                            record.wind_direction if record.wind_direction else 'N/A'
                        ])
                    if include_precip:
                        row.extend([
                            record.precipitation_rate if record.precipitation_rate else 'N/A',
                            record.precipitation_total if record.precipitation_total else 'N/A'
                        ])
                    
                    station_data.append({'row': row, 'station': station.name})
            else:
                # Add a row even if no records
                row = [
                    station.name,
                    station.station_id,
                    station.latitude if station.latitude is not None else 'N/A',
                    station.longitude if station.longitude is not None else 'N/A',
                    station.status,
                    'N/A',
                    'N/A'
                ]
                if include_temp:
                    row.append('N/A')
                if include_humidity:
                    row.append('N/A')
                if include_wind:
                    row.extend(['N/A', 'N/A'])
                if include_precip:
                    row.extend(['N/A', 'N/A'])
                station_data.append({'row': row, 'station': station.name})
        
        # Add all rows to report data
        for data in station_data:
            report_data.append(data['row'])
    else:
        messages.error(request, 'Invalid report type')
        return redirect('settings')
    
    # Handle chart format type for water level reports
    if format_type == 'chart' and report_type == 'water_level':
        # Get the station object
        station = stations[0]
        
        # Prepare the chart data
        chart_data = {}
        dates = []
        levels = []
        
        # Collect data points for the chart
        for data in station_data:
            if data['reading']:
                reading = data['reading']
                # Create datetime object for proper sorting and display
                date_time = datetime.combine(reading.date, reading.time)
                dates.append(date_time)
                levels.append(reading.data)
        
        # If no data points, show an error
        if not dates:
            messages.error(request, f'No data available for the selected station in the date range')
            return redirect('settings')
        
        # Sort data by date/time
        sorted_data = sorted(zip(dates, levels))
        dates = [item[0] for item in sorted_data]
        levels = [item[1] for item in sorted_data]
        
        # Create a chart using matplotlib
        plt.figure(figsize=(12, 6))
        
        # Set chart style
        plt.style.use('seaborn-v0_8-whitegrid')
        
        # Plot the water level data
        plt.plot(dates, levels, marker='o', linestyle='-', color='#024CAA', linewidth=2, markersize=4)
        
        # Add data annotations on the chart
        for i, (date, level) in enumerate(zip(dates, levels)):
            # Add value labels to each point, but skip some if there are too many points
            if len(dates) <= 20 or i % max(1, len(dates) // 10) == 0:
                plt.annotate(f'{level:.1f}', 
                            xy=(date, level),
                            xytext=(0, 10),  # Offset text 10 points above
                            textcoords='offset points',
                            ha='center',
                            fontsize=9,
                            bbox=dict(boxstyle='round,pad=0.3', fc='white', alpha=0.7),
                            arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0.0', color='gray'))
        
        # Add threshold lines
        plt.axhline(y=station.green_threshold, color='#10B981', linestyle='--', alpha=0.7, label=f'Green Threshold ({station.green_threshold} cm)')
        plt.axhline(y=station.yellow_threshold, color='#F59E0B', linestyle='--', alpha=0.7, label=f'Yellow Threshold ({station.yellow_threshold} cm)')
        plt.axhline(y=station.orange_threshold, color='#F97316', linestyle='--', alpha=0.7, label=f'Orange Threshold ({station.orange_threshold} cm)')
        plt.axhline(y=station.red_threshold, color='#DC2626', linestyle='--', alpha=0.7, label=f'Red Threshold ({station.red_threshold} cm)')
        
        # Set chart title and labels
        plt.title(f'Water Level Data for {station.name}', fontsize=16, pad=20)
        plt.xlabel('Date/Time', fontsize=12, labelpad=10)
        plt.ylabel('Water Level (cm)', fontsize=12, labelpad=10)
        
        # Format x-axis dates
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.gcf().autofmt_xdate()
        
        # Add legend
        plt.legend(loc='best')
        
        # Add grid
        plt.grid(True, alpha=0.3)
        
        # Tight layout
        plt.tight_layout()
        
        # Save the chart to a buffer
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=100)
        buffer.seek(0)
        chart_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        plt.close()
        
        # Render the chart template with the chart image
        context = {
            'chart_image': chart_image,
            'station': station,
            'date_from': date_from.strftime('%Y-%m-%d'),
            'date_to': (date_to - timedelta(days=1)).strftime('%Y-%m-%d'),
            'num_readings': len(dates),
            'min_level': min(levels) if levels else 0,
            'max_level': max(levels) if levels else 0,
            'avg_level': sum(levels) / len(levels) if levels else 0,
            'data_points': [
                {
                    'date': dates[i].strftime('%Y-%m-%d'),
                    'time': dates[i].strftime('%H:%M:%S'),
                    'level': levels[i]
                } for i in range(len(dates))
            ]
        }
        
        return render(request, 'water_level_chart.html', context)
        
    # Generate the report in the requested format
    elif format_type == 'pdf':
        # Create PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
        elements = []
        
        # Add title
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=10,
            alignment=1  # Center alignment
        )
        title = Paragraph(f"{'Water Level' if report_type == 'water_level' else 'Weather'} Stations Report", title_style)
        elements.append(title)
        
        # Add date range
        date_style = ParagraphStyle(
            'DateRange',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            alignment=1  # Center alignment
        )
        date_range = Paragraph(
            f"Period: {date_from.strftime('%Y-%m-%d')} to {(date_to - timedelta(days=1)).strftime('%Y-%m-%d')}",
            date_style
        )
        elements.append(date_range)
        
        # Create table
        table = Table(report_data)
        
        # Style the table based on report type
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#024CAA')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]
        
        # Add conditional formatting based on report type
        if report_type == 'water_level':
            # Add color formatting for alert status column
            for i in range(1, len(report_data)):
                alert_status = report_data[i][-1]
                if alert_status == 'Critical (Red)':
                    table_style.append(('BACKGROUND', (-1, i), (-1, i), colors.HexColor('#FFCCCC')))
                    table_style.append(('TEXTCOLOR', (-1, i), (-1, i), colors.HexColor('#DC2626')))
                elif alert_status == 'High (Orange)':
                    table_style.append(('BACKGROUND', (-1, i), (-1, i), colors.HexColor('#FFEACC')))
                    table_style.append(('TEXTCOLOR', (-1, i), (-1, i), colors.HexColor('#FB923C')))
                elif alert_status == 'Medium (Yellow)':
                    table_style.append(('BACKGROUND', (-1, i), (-1, i), colors.HexColor('#FFF9CC')))
                    table_style.append(('TEXTCOLOR', (-1, i), (-1, i), colors.HexColor('#D97706')))
                elif alert_status == 'Low (Green)':
                    table_style.append(('BACKGROUND', (-1, i), (-1, i), colors.HexColor('#CCFFE5')))
                    table_style.append(('TEXTCOLOR', (-1, i), (-1, i), colors.HexColor('#10B981')))
        
        # Add station group headers to visually separate stations
        current_station = None
        for i in range(1, len(report_data)):
            station_name = report_data[i][0]
            if station_name != current_station:
                current_station = station_name
                table_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#E6F0FF')))
                table_style.append(('FONTNAME', (0, i), (-1, i), 'Helvetica-Bold'))
        
        table.setStyle(TableStyle(table_style))
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        
        # Prepare response
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        filename = f"{report_type}_report_{date_from.strftime('%Y%m%d')}_{(date_to - timedelta(days=1)).strftime('%Y%m%d')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
    else:  # Excel format
        # Create Excel file
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer)
        worksheet = workbook.add_worksheet()
        
        # Define formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        date_format = workbook.add_format({
            'font_size': 12,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        header_format = workbook.add_format({
            'bold': True,
            'font_color': 'white',
            'bg_color': '#024CAA',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        station_header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E6F0FF',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        # Alert status formats for water level reports
        red_format = workbook.add_format({
            'bg_color': '#FFCCCC',
            'font_color': '#DC2626',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        orange_format = workbook.add_format({
            'bg_color': '#FFEACC',
            'font_color': '#FB923C',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        yellow_format = workbook.add_format({
            'bg_color': '#FFF9CC',
            'font_color': '#D97706',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        green_format = workbook.add_format({
            'bg_color': '#CCFFE5',
            'font_color': '#10B981',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        normal_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        # Add title
        worksheet.merge_range('A1:G1', f"{'Water Level' if report_type == 'water_level' else 'Weather'} Stations Report", title_format)
        
        # Add date range
        worksheet.merge_range('A2:G2', f"Period: {date_from.strftime('%Y-%m-%d')} to {(date_to - timedelta(days=1)).strftime('%Y-%m-%d')}", date_format)
        
        # Write data
        current_station = None
        for row_idx, row in enumerate(report_data):
            for col_idx, value in enumerate(row):
                if row_idx == 0:  # Headers
                    worksheet.write(row_idx + 3, col_idx, value, header_format)
                    worksheet.set_column(col_idx, col_idx, 15)  # Set column width
                else:  # Data
                    # Check if this is a new station
                    if col_idx == 0 and row[0] != current_station:
                        current_station = row[0]
                        # Apply station header format to the first row of each station
                        for c in range(len(row)):
                            worksheet.write(row_idx + 3, c, row[c], station_header_format)
                        continue
                    
                    # Apply special formatting for alert status column in water level reports
                    if report_type == 'water_level' and col_idx == len(row) - 1:
                        if value == 'Critical (Red)':
                            worksheet.write(row_idx + 3, col_idx, value, red_format)
                        elif value == 'High (Orange)':
                            worksheet.write(row_idx + 3, col_idx, value, orange_format)
                        elif value == 'Medium (Yellow)':
                            worksheet.write(row_idx + 3, col_idx, value, yellow_format)
                        elif value == 'Low (Green)':
                            worksheet.write(row_idx + 3, col_idx, value, green_format)
                        else:
                            worksheet.write(row_idx + 3, col_idx, value, normal_format)
                    else:
                        worksheet.write(row_idx + 3, col_idx, value, normal_format)
        
        workbook.close()
        
        # Prepare response
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        filename = f"{report_type}_report_{date_from.strftime('%Y%m%d')}_{(date_to - timedelta(days=1)).strftime('%Y%m%d')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

@login_required
def station_map(request):
    """
    View function for the stations map page showing both Water Level and Weather stations.
    """
    # Get active stations with coordinates
    water_stations = WaterLevelStation.objects.filter(
        status='active'
    ).exclude(
        latitude__isnull=True
    ).exclude(
        longitude__isnull=True
    )
    
    weather_stations = WeatherStation.objects.filter(
        status='active'
    ).exclude(
        latitude__isnull=True
    ).exclude(
        longitude__isnull=True
    )
    
    # Prepare stations data for the map
    stations_data = []
    
    # Add water level stations with latest data
    for station in water_stations:
        latest_data = station.data.first()  # Get the latest water level reading
        
        # Determine alert level based on thresholds
        alert_level = "normal"
        if latest_data:
            if latest_data.data > station.red_threshold:
                alert_level = "red"
            elif latest_data.data > station.orange_threshold:
                alert_level = "orange"
            elif latest_data.data > station.yellow_threshold:
                alert_level = "yellow"
            elif latest_data.data > station.green_threshold:
                alert_level = "green"
        
        station_info = {
            'id': station.id,
            'name': station.name,
            'station_id': station.station_id,
            'type': 'water',
            'latitude': station.latitude,
            'longitude': station.longitude,
            'last_reading': latest_data.data if latest_data else None,
            'last_reading_time': f"{latest_data.date} {latest_data.time}" if latest_data else None,
            'alert_level': alert_level,
            'green_threshold': station.green_threshold,
            'yellow_threshold': station.yellow_threshold,
            'orange_threshold': station.orange_threshold,
            'red_threshold': station.red_threshold
        }
        stations_data.append(station_info)
    
    # Add weather stations with latest data
    for station in weather_stations:
        latest_weather = station.weather_logs.first()  # Get the latest weather reading
        
        # Format weather values to one decimal place
        temperature = None
        humidity = None
        wind_speed = None
        precipitation_rate = None
        
        if latest_weather:
            try:
                temperature = float(latest_weather.temperature)
                temperature = f"{temperature:.1f}"
            except (ValueError, TypeError):
                temperature = latest_weather.temperature
                
            try:
                humidity = float(latest_weather.humidity)
                humidity = f"{humidity:.1f}"
            except (ValueError, TypeError):
                humidity = latest_weather.humidity
                
            try:
                wind_speed = float(latest_weather.wind_speed)
                wind_speed = f"{wind_speed:.1f}"
            except (ValueError, TypeError):
                wind_speed = latest_weather.wind_speed
                
            try:
                precipitation_rate = float(latest_weather.precipitation_rate)
                precipitation_rate = f"{precipitation_rate:.1f}"
            except (ValueError, TypeError):
                precipitation_rate = latest_weather.precipitation_rate
        
        weather_info = {
            'id': station.id,
            'name': station.name,
            'station_id': station.station_id,
            'type': 'weather',
            'latitude': station.latitude,
            'longitude': station.longitude,
            'temperature': temperature,
            'humidity': humidity,
            'wind_speed': wind_speed,
            'wind_direction': latest_weather.wind_direction if latest_weather else None,
            'pressure': latest_weather.pressure if latest_weather else None,
            'precipitation_rate': precipitation_rate,
            'last_update': latest_weather.timestamp.strftime("%Y-%m-%d %H:%M:%S") if latest_weather else None
        }
        stations_data.append(weather_info)
    
    # Determine map center based on average coordinates of all stations
    all_lats = [s['latitude'] for s in stations_data if s['latitude'] is not None]
    all_longs = [s['longitude'] for s in stations_data if s['longitude'] is not None]
    
    map_center = {
        'latitude': sum(all_lats) / len(all_lats) if all_lats else 10.3157,  # Default to coordinates 
        'longitude': sum(all_longs) / len(all_longs) if all_longs else 123.8854  # in the Philippines if no stations
    }
    
    # Generate log entry
    if request.user.is_authenticated:
        Logs.objects.create(
            user=request.user,
            action="Viewed station map"
        )
    
    context = {
        'stations_data': json.dumps(stations_data),
        'map_center': map_center,
        'water_stations_count': water_stations.count(),
        'weather_stations_count': weather_stations.count()
    }
    
    return render(request, 'station_map.html', context)

@login_required
def get_station_updates(request):
    """
    API endpoint to get the latest data for all stations for the map
    """
    # Get station IDs from request
    water_station_ids = request.GET.getlist('water_stations[]', [])
    weather_station_ids = request.GET.getlist('weather_stations[]', [])
    
    updates = {}
    
    # Get water level station updates
    if water_station_ids:
        for station_id in water_station_ids:
            try:
                station = WaterLevelStation.objects.get(id=station_id)
                latest_data = station.data.first()
                
                if latest_data:
                    # Determine alert level
                    alert_level = "normal"
                    if latest_data.data > station.red_threshold:
                        alert_level = "red"
                    elif latest_data.data > station.orange_threshold:
                        alert_level = "orange"
                    elif latest_data.data > station.yellow_threshold:
                        alert_level = "yellow"
                    elif latest_data.data > station.green_threshold:
                        alert_level = "green"
                    
                    updates[f"water_{station_id}"] = {
                        'reading': latest_data.data,
                        'time': f"{latest_data.date} {latest_data.time}",
                        'alert_level': alert_level
                    }
            except WaterLevelStation.DoesNotExist:
                pass
    
    # Get weather station updates
    if weather_station_ids:
        for station_id in weather_station_ids:
            try:
                station = WeatherStation.objects.get(id=station_id)
                latest_weather = station.weather_logs.first()
                
                if latest_weather:
                    # Format weather values to one decimal place
                    try:
                        temperature = float(latest_weather.temperature)
                        temperature = f"{temperature:.1f}"
                    except (ValueError, TypeError):
                        temperature = latest_weather.temperature
                        
                    try:
                        humidity = float(latest_weather.humidity)
                        humidity = f"{humidity:.1f}"
                    except (ValueError, TypeError):
                        humidity = latest_weather.humidity
                        
                    try:
                        wind_speed = float(latest_weather.wind_speed)
                        wind_speed = f"{wind_speed:.1f}"
                    except (ValueError, TypeError):
                        wind_speed = latest_weather.wind_speed
                        
                    try:
                        precipitation_rate = float(latest_weather.precipitation_rate)
                        precipitation_rate = f"{precipitation_rate:.1f}"
                    except (ValueError, TypeError):
                        precipitation_rate = latest_weather.precipitation_rate
                    
                    updates[f"weather_{station_id}"] = {
                        'temperature': temperature,
                        'humidity': humidity,
                        'wind_speed': wind_speed,
                        'wind_direction': latest_weather.wind_direction,
                        'precipitation_rate': precipitation_rate,
                        'time': latest_weather.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    }
            except WeatherStation.DoesNotExist:
                pass
    
    return JsonResponse({'status': 'success', 'updates': updates})



