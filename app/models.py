from django.db import models
from django.contrib.auth.models import User 



class WaterLevelStation(models.Model):
    name = models.CharField(max_length=255)  # Station name (e.g., "Pagatban Bridge")
    station_id = models.CharField(max_length=255, unique=True)  # Unique identifier
    green_threshold = models.FloatField()
    yellow_threshold = models.FloatField()
    orange_threshold = models.FloatField() 
    red_threshold = models.FloatField()
    modbus_ip = models.GenericIPAddressField(protocol='IPv4')
    modbus_port = models.IntegerField(default=100)
    unit_id = models.IntegerField(default=1)
    register_address = models.IntegerField(default=6)
    status = models.CharField(max_length=255, default="active")
    date_created = models.DateTimeField(auto_now_add=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.station_id})"
    
    
# Data records for custom water level stations
class WaterLevelData(models.Model):
    station = models.ForeignKey(WaterLevelStation, on_delete=models.CASCADE, related_name='data')
    date = models.DateField(auto_now_add=True)
    time = models.TimeField(auto_now_add=True)
    data = models.FloatField()  # Stores water level in centimeters
    type = models.CharField(max_length=255, default="live")
    
    class Meta:
        ordering = ['-date', '-time']
        
    def __str__(self):
        return f"{self.station.name} - {self.date} {self.time} - {self.data} cm"
    
    
class WeatherStation(models.Model):
    name = models.CharField(max_length=255)
    station_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=255, default="active")
    date_added = models.DateTimeField(auto_now_add=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.station_id})"
    

class WeatherStatus(models.Model):
    weather_station = models.ForeignKey(WeatherStation, on_delete=models.CASCADE, related_name='weather_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    temperature = models.CharField(max_length=255, null=True, blank=True)
    humidity = models.CharField(max_length=255, null=True, blank=True)
    wind_speed = models.CharField(max_length=255, null=True, blank=True)
    wind_direction = models.CharField(max_length=255, null=True, blank=True)
    pressure = models.CharField(max_length=255, null=True, blank=True)
    precipitation_rate = models.CharField(max_length=255, null=True, blank=True)
    precipitation_total = models.CharField(max_length=255, null=True, blank=True)
    uv = models.CharField(max_length=255, null=True, blank=True)
    solar_radiation = models.CharField(max_length=255, null=True, blank=True)
    data_source = models.CharField(max_length=255, default="api")  # 'api' or 'manual'

    class Meta:
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.weather_station.name} - {self.timestamp} - {self.temperature}°C"
    

class WeatherForecastStation(models.Model):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)  # Location name (e.g., "Dumaguete City")
    latitude = models.FloatField()  # Latitude for Open-Meteo API
    longitude = models.FloatField()  # Longitude for Open-Meteo API
    status = models.CharField(max_length=255, default="active")
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.location})"


class WeatherForecast(models.Model):
    forecast_station = models.ForeignKey(WeatherForecastStation, on_delete=models.CASCADE, related_name='forecasts')
    timestamp = models.DateTimeField()  # The time of the forecast
    temperature = models.FloatField(null=True, blank=True)  # Temperature in °C
    precipitation_probability = models.FloatField(null=True, blank=True)  # Precipitation probability in %
    relative_humidity = models.FloatField(null=True, blank=True)  # Relative humidity in %
    dew_point = models.FloatField(null=True, blank=True)  # Dew point in °C
    fetch_time = models.DateTimeField(auto_now_add=True)  # When the forecast was fetched

    class Meta:
        ordering = ['timestamp']
        
    def __str__(self):
        return f"{self.forecast_station.name} - {self.timestamp} - {self.temperature}°C"


class Logs(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.timestamp}"
    
