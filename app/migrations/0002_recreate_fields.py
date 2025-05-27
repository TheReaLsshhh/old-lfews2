from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='waterlevelstation',
            name='name',
        ),
        migrations.RemoveField(
            model_name='waterlevelstation',
            name='station_id',
        ),
        migrations.RemoveField(
            model_name='waterlevelstation',
            name='status',
        ),
        migrations.AddField(
            model_name='waterlevelstation',
            name='name',
            field=models.CharField(max_length=100, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='waterlevelstation',
            name='station_id',
            field=models.CharField(max_length=50, unique=True, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='waterlevelstation',
            name='status',
            field=models.CharField(default='active', max_length=100),
        ),
    ] 