-- Alter column lengths for app_waterlevelstation table
ALTER TABLE app_waterlevelstation ALTER COLUMN name TYPE varchar(100);
ALTER TABLE app_waterlevelstation ALTER COLUMN station_id TYPE varchar(50);
ALTER TABLE app_waterlevelstation ALTER COLUMN status TYPE varchar(100); 