# Generated migration for adding UID photo fields to UjjwalaV3FamilyMember
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ujjwala_v3', '0001_initial'),
    ]

    operations = [
        # Add UID photo URL fields
        migrations.AddField(
            model_name='ujjwalav3familymember',
            name='uid_front_link',
            field=models.URLField(blank=True, help_text='URL to Aadhaar/UID front photo (compressed)', max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='ujjwalav3familymember',
            name='uid_back_link',
            field=models.URLField(blank=True, help_text='URL to Aadhaar/UID back photo (compressed)', max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='ujjwalav3familymember',
            name='uid_original_front_link',
            field=models.URLField(blank=True, help_text='URL to original uncompressed Aadhaar/UID front photo', max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='ujjwalav3familymember',
            name='uid_original_back_link',
            field=models.URLField(blank=True, help_text='URL to original uncompressed Aadhaar/UID back photo', max_length=500, null=True),
        ),

        # Add OCR processing result fields
        migrations.AddField(
            model_name='ujjwalav3familymember',
            name='uid_check_result',
            field=models.JSONField(blank=True, help_text='OCR results from Zoho Catalyst containing extracted Aadhaar data (name, DOB, gender, address, etc.)', null=True),
        ),
        migrations.AddField(
            model_name='ujjwalav3familymember',
            name='is_valid_uid',
            field=models.BooleanField(default=False, help_text='Whether UID/Aadhaar validation passed'),
        ),
        migrations.AddField(
            model_name='ujjwalav3familymember',
            name='validated',
            field=models.BooleanField(default=False, help_text='Whether family member data has been validated'),
        ),

        # Add file metadata fields
        migrations.AddField(
            model_name='ujjwalav3familymember',
            name='uid_front_compressed',
            field=models.BooleanField(default=False, help_text='Whether front UID photo has been compressed'),
        ),
        migrations.AddField(
            model_name='ujjwalav3familymember',
            name='uid_back_compressed',
            field=models.BooleanField(default=False, help_text='Whether back UID photo has been compressed'),
        ),
        migrations.AddField(
            model_name='ujjwalav3familymember',
            name='uid_front_file_size',
            field=models.CharField(blank=True, help_text='File size of front UID photo (e.g., "1.2 MB")', max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='ujjwalav3familymember',
            name='uid_back_file_size',
            field=models.CharField(blank=True, help_text='File size of back UID photo (e.g., "1.5 MB")', max_length=50, null=True),
        ),

        # Add additional details fields
        migrations.AddField(
            model_name='ujjwalav3familymember',
            name='additional_details',
            field=models.JSONField(blank=True, help_text='Additional details like profession, company name, etc.', null=True),
        ),
        migrations.AddField(
            model_name='ujjwalav3familymember',
            name='ration_card_available',
            field=models.BooleanField(default=False, help_text='Whether family member has ration card'),
        ),
    ]
