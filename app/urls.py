from django.contrib import admin
from django.urls import path
from . import views
from django.shortcuts import redirect

urlpatterns = [
    path('root-redirect/', views.root_redirect),
    path('', views.admin_login, name='admin_login'),  # Handle root URL with login
    path('admin-login/', views.admin_login, name='admin_login'),  # Handle direct admin-login URL
    path('logout/', views.admin_logout, name='admin_logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('fetch-water-level/', views.fetch_water_level, name='fetch_water_level'),
    path('settings/', views.settings_view, name='settings'),
    path('weather-updates/', views.weather_updates, name='weather_updates'),
    path('fetch-weather-data/', views.fetch_weather_data, name='fetch_weather_data'),
    path('weather-forecast/', views.weather_forecast, name='weather_forecast'),
    path('fetch-forecast-data/', views.fetch_forecast_data, name='fetch_forecast_data'),
    path('activity-logs/', views.activity_logs, name='activity_logs'),
    path('generate-report/', views.generate_report, name='generate_report'),
    path('station-map/', views.station_map, name='station_map'),
    path('get-station-updates/', views.get_station_updates, name='get_station_updates'),
    
    path('register-sub-admin/', views.register_sub_admin, name='register_sub_admin'),
]
