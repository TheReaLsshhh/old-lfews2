from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='waterlevelstation',
            name='name',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='waterlevelstation',
            name='station_id',
            field=models.CharField(max_length=255, unique=True),
        ),
        migrations.AlterField(
            model_name='waterlevelstation',
            name='status',
            field=models.CharField(default='active', max_length=255),
        ),
    ] 