# Generated manually for ujjwala_v3
# Add UID photo fields and OCR results to FamilyMember model

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django_fsm


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UjjwalaV3Application',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('applicant_full_name', models.CharField(db_index=True, help_text='Full name of applicant as per Aadhaar', max_length=200, validators=[django.core.validators.RegexValidator('^[A-Za-z\\s\\-\\.\']+$', 'Only letters, spaces, hyphens, periods and apostrophes allowed')])),
                ('applicant_first_name', models.CharField(help_text='First name of applicant', max_length=100, validators=[django.core.validators.RegexValidator('^[A-Za-z\\s\\-\\.\']+$', 'Only letters, spaces, hyphens, periods and apostrophes allowed')])),
                ('applicant_middle_name', models.CharField(blank=True, help_text='Middle name of applicant (optional)', max_length=100, null=True, validators=[django.core.validators.RegexValidator('^[A-Za-z\\s\\-\\.\']+$', 'Only letters, spaces, hyphens, periods and apostrophes allowed')])),
                ('applicant_last_name', models.CharField(blank=True, help_text='Last name of applicant (optional)', max_length=100, null=True, validators=[django.core.validators.RegexValidator('^[A-Za-z\\s\\-\\.\']+$', 'Only letters, spaces, hyphens, periods and apostrophes allowed')])),
                ('applicant_gender', models.CharField(choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], default='F', help_text='Gender - Must be Female for PMUY V3', max_length=1)),
                ('applicant_dob', models.DateField(db_index=True, help_text='Date of birth as per Aadhaar (Must be >= 18 years)')),
                ('applicant_aadhaar_number', models.CharField(db_index=True, help_text='12-digit Aadhaar number (unique)', max_length=12, unique=True, validators=[django.core.validators.RegexValidator('^[2-9][0-9]{11}$', 'Aadhaar must be 12 digits and cannot start with 0 or 1'), django.core.validators.MinLengthValidator(12), django.core.validators.MaxLengthValidator(12)])),
                ('applicant_mobile', models.CharField(db_index=True, help_text='10-digit mobile number', max_length=10, validators=[django.core.validators.RegexValidator('^[6-9][0-9]{9}$', 'Mobile number must be 10 digits starting with 6, 7, 8, or 9'), django.core.validators.MinLengthValidator(10), django.core.validators.MaxLengthValidator(10)])),
                ('applicant_email', models.EmailField(blank=True, db_index=True, help_text='Email address (optional)', max_length=254, null=True)),
                ('caste', models.CharField(choices=[('SC', 'Scheduled Caste'), ('ST', 'Scheduled Tribe'), ('OBC', 'Other Backward Class'), ('GENERAL', 'General'), ('OTHERS', 'Others')], db_index=True, default='GENERAL', help_text='Caste/Category as per government classification', max_length=20)),
                ('is_migrant', models.BooleanField(default=True, help_text='Migrant status - Must be True for PMUY V3')),
                ('family_doc_issuing_state', models.CharField(blank=True, db_index=True, help_text='State that issued the family composition document (e.g., Punjab)', max_length=100, null=True)),
                ('family_doc_type', models.CharField(blank=True, choices=[('RATION_CARD', 'Ration Card'), ('SELF_DECLARATION_MIGRANT', 'Self Declaration (Migrant)'), ('OTHER', 'Other Document')], help_text='Type of family composition document', max_length=50, null=True)),
                ('family_doc_number', models.CharField(blank=True, help_text='Document number of family composition document', max_length=100, null=True)),
                ('is_deprivation_decl_signed', models.BooleanField(default=False, help_text='Whether deprivation declaration has been signed')),
                ('bank_account_name', models.CharField(help_text='Account holder name as per bank records', max_length=200, validators=[django.core.validators.RegexValidator('^[A-Za-z\\s\\-\\.\']+$', 'Only letters, spaces, hyphens, periods and apostrophes allowed')])),
                ('bank_name', models.CharField(help_text='Name of the bank', max_length=200)),
                ('bank_branch', models.CharField(help_text='Bank branch name', max_length=200)),
                ('bank_ifsc', models.CharField(db_index=True, help_text='11-character IFSC code', max_length=11, validators=[django.core.validators.RegexValidator('^[A-Z]{4}0[A-Z0-9]{6}$', 'Invalid IFSC code format'), django.core.validators.MinLengthValidator(11), django.core.validators.MaxLengthValidator(11)])),
                ('bank_account_number', models.CharField(help_text='Bank account number (9-18 characters)', max_length=18, validators=[django.core.validators.RegexValidator('^[0-9]{9,18}$', 'Bank account number must be 9-18 digits')])),
                ('lpg_connection_type', models.CharField(choices=[('SINGLE_14_2KG', 'Single 14.2 KG Cylinder'), ('SINGLE_5KG', 'Single 5 KG Cylinder'), ('DOUBLE_5KG', 'Double 5 KG Cylinders')], db_index=True, default='SINGLE_14_2KG', help_text='Type of LPG connection/cylinder', max_length=20)),
                ('application_number', models.CharField(blank=True, db_index=True, help_text='Unique application reference number (auto-generated)', max_length=50, null=True, unique=True)),
                ('status', django_fsm.FSMField(choices=[('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'), ('UNDER_VERIFICATION', 'Under Verification'), ('VERIFICATION_FAILED', 'Verification Failed'), ('REJECTED', 'Rejected'), ('APPROVED', 'Approved'), ('CONNECTION_ISSUED', 'Connection Issued'), ('CANCELLED', 'Cancelled'), ('ON_HOLD', 'On Hold')], db_index=True, default='DRAFT', help_text='Current status of the application (FSM-controlled)', max_length=30)),
                ('rejection_reason', models.TextField(blank=True, help_text='Reason for rejection if status is REJECTED', null=True)),
                ('submitted_at', models.DateTimeField(blank=True, db_index=True, help_text='Timestamp when application was submitted', null=True)),
                ('verified_at', models.DateTimeField(blank=True, help_text='Timestamp when application verification completed', null=True)),
                ('approved_at', models.DateTimeField(blank=True, help_text='Timestamp when application was approved', null=True)),
                ('connection_issued_at', models.DateTimeField(blank=True, help_text='Timestamp when LPG connection was issued', null=True)),
                ('verification_started_at', models.DateTimeField(blank=True, help_text='Timestamp when verification process started', null=True)),
                ('rejected_at', models.DateTimeField(blank=True, help_text='Timestamp when application was rejected', null=True)),
                ('aadhaar_verification_status', models.CharField(choices=[('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'), ('VERIFIED', 'Verified'), ('FAILED', 'Failed'), ('SKIPPED', 'Skipped')], default='PENDING', help_text='Status of Aadhaar verification', max_length=20)),
                ('bank_verification_status', models.CharField(choices=[('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'), ('VERIFIED', 'Verified'), ('FAILED', 'Failed'), ('SKIPPED', 'Skipped')], default='PENDING', help_text='Status of bank account verification', max_length=20)),
                ('address_verification_status', models.CharField(choices=[('PENDING', 'Pending'), ('IN_PROGRESS', 'In Progress'), ('VERIFIED', 'Verified'), ('FAILED', 'Failed'), ('SKIPPED', 'Skipped')], default='PENDING', help_text='Status of address verification', max_length=20)),
                ('approved_by', models.ForeignKey(blank=True, help_text='User who approved the application', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_ujjwala_v3_applications', to=settings.AUTH_USER_MODEL)),
                ('submitted_by', models.ForeignKey(blank=True, help_text='User who submitted the application', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='submitted_ujjwala_v3_applications', to=settings.AUTH_USER_MODEL)),
                ('verified_by', models.ForeignKey(blank=True, help_text='User who verified the application', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='verified_ujjwala_v3_applications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Ujjwala V3 Application',
                'verbose_name_plural': 'Ujjwala V3 Applications',
                'db_table': 'ujjwala_v3_application',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['status', 'created_at'], name='ujjwala_v3_status_created_idx'),
                    models.Index(fields=['applicant_mobile', 'status'], name='ujjwala_v3_mobile_status_idx'),
                    models.Index(fields=['applicant_aadhaar_number'], name='ujjwala_v3_aadhaar_idx'),
                    models.Index(fields=['application_number'], name='ujjwala_v3_app_number_idx'),
                    models.Index(fields=['submitted_at'], name='ujjwala_v3_submitted_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='UjjwalaV3Address',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('address_type', models.CharField(choices=[('CURRENT', 'Current Address (Connection Location)'), ('PERMANENT', 'Permanent Address (As per Aadhaar)'), ('OTHER', 'Other Address')], db_index=True, help_text='Type of address (CURRENT, PERMANENT, OTHER)', max_length=20)),
                ('house_flat_no', models.CharField(help_text='House/Flat number', max_length=50)),
                ('floor_number', models.CharField(blank=True, help_text='Floor number (if applicable)', max_length=20, null=True)),
                ('building_colony', models.CharField(blank=True, help_text='Building/Colony/Apartment name', max_length=200, null=True)),
                ('street_road', models.CharField(blank=True, help_text='Street/Road name', max_length=200, null=True)),
                ('village_panchayat_area', models.CharField(blank=True, help_text='Village/Panchayat/Area/Locality', max_length=200, null=True)),
                ('block_sub_district', models.CharField(blank=True, help_text='Block/Sub-district/Tehsil', max_length=200, null=True)),
                ('district', models.CharField(db_index=True, help_text='District', max_length=200)),
                ('city_town', models.CharField(db_index=True, help_text='City/Town/Municipality', max_length=200)),
                ('state', models.CharField(db_index=True, help_text='State/UT name (e.g., Punjab, Haryana)', max_length=100)),
                ('pincode', models.CharField(db_index=True, help_text='6-digit pincode', max_length=6, validators=[django.core.validators.RegexValidator('^[1-9][0-9]{5}$', 'Pincode must be 6 digits and cannot start with 0'), django.core.validators.MinLengthValidator(6), django.core.validators.MaxLengthValidator(6)])),
                ('landmark', models.CharField(blank=True, help_text='Nearby landmark', max_length=200, null=True)),
                ('area_post_office_name', models.CharField(blank=True, help_text='Post office name', max_length=200, null=True)),
                ('poa_code', models.CharField(choices=[('POA01', 'POA01 - Aadhaar Card'), ('POA02', 'POA02 - Passport'), ('POA03', 'POA03 - Voter ID Card'), ('POA04', 'POA04 - Driving License'), ('POA05', 'POA05 - Electricity Bill (< 2 months)'), ('POA06', 'POA06 - Telephone Bill (< 2 months)'), ('POA07', 'POA07 - Water Bill (< 2 months)'), ('POA08', 'POA08 - Bank Statement (< 3 months)'), ('POA09', 'POA09 - Ration Card'), ('POA10', 'POA10 - Property Tax Receipt'), ('POA11', 'POA11 - Rent Agreement (registered)'), ('POA12', 'POA12 - Employer Certificate (with address)'), ('POA13', 'POA13 - Gas Connection Bill'), ('POA14', 'POA14 - Broadband Bill (< 2 months)'), ('POA15', 'POA15 - Post Office Passbook'), ('POA16', 'POA16 - Insurance Policy'), ('POA17', 'POA17 - Domicile Certificate'), ('POA18', 'POA18 - Marriage Certificate'), ('POA19', 'POA19 - Birth Certificate'), ('POA20', 'POA20 - School/College ID Card'), ('POA21', 'POA21 - Municipal/Panchayat Certificate'), ('POA22', 'POA22 - Revenue Record (Patawari/Tehsildar)'), ('POA23', 'POA23 - Arms License'), ('POA24', 'POA24 - Court Order/Decree'), ('POA25', 'POA25 - Migrant Certificate / Other Government-issued Document')], help_text='Proof of Address document code (POA01-POA25)', max_length=10)),
                ('latitude', models.DecimalField(blank=True, decimal_places=8, help_text='Latitude coordinate', max_digits=10, null=True)),
                ('longitude', models.DecimalField(blank=True, decimal_places=8, help_text='Longitude coordinate', max_digits=11, null=True)),
                ('application', models.ForeignKey(help_text='Related application', on_delete=django.db.models.deletion.CASCADE, related_name='addresses', to='ujjwala_v3.ujjwalav3application')),
            ],
            options={
                'verbose_name': 'Ujjwala V3 Address',
                'verbose_name_plural': 'Ujjwala V3 Addresses',
                'db_table': 'ujjwala_v3_address',
                'ordering': ['address_type', '-created_at'],
                'indexes': [
                    models.Index(fields=['application', 'address_type'], name='ujjwala_v3_addr_app_type_idx'),
                    models.Index(fields=['state', 'district'], name='ujjwala_v3_addr_state_dist_idx'),
                    models.Index(fields=['pincode'], name='ujjwala_v3_addr_pincode_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='UjjwalaV3FamilyMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('full_name', models.CharField(help_text='Full name as per Aadhaar', max_length=200, validators=[django.core.validators.RegexValidator('^[A-Za-z\\s\\-\\.\']+$', 'Only letters, spaces, hyphens, periods and apostrophes allowed')])),
                ('relation_to_applicant', models.CharField(choices=[('SELF', 'Self (Applicant)'), ('FATHER', 'Father'), ('MOTHER', 'Mother'), ('HUSBAND', 'Husband'), ('WIFE', 'Wife'), ('SON', 'Son'), ('DAUGHTER', 'Daughter'), ('BROTHER', 'Brother'), ('SISTER', 'Sister'), ('GRANDFATHER', 'Grandfather'), ('GRANDMOTHER', 'Grandmother'), ('GRANDSON', 'Grandson'), ('GRANDDAUGHTER', 'Granddaughter'), ('UNCLE', 'Uncle'), ('AUNT', 'Aunt'), ('NEPHEW', 'Nephew'), ('NIECE', 'Niece'), ('FATHER_IN_LAW', 'Father-in-law'), ('MOTHER_IN_LAW', 'Mother-in-law'), ('SON_IN_LAW', 'Son-in-law'), ('DAUGHTER_IN_LAW', 'Daughter-in-law'), ('OTHER', 'Other Relation')], db_index=True, help_text='Relationship to applicant', max_length=20)),
                ('gender', models.CharField(choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], help_text='Gender', max_length=1)),
                ('aadhaar_number', models.CharField(db_index=True, help_text='12-digit Aadhaar number', max_length=12, validators=[django.core.validators.RegexValidator('^[2-9][0-9]{11}$', 'Aadhaar must be 12 digits and cannot start with 0 or 1'), django.core.validators.MinLengthValidator(12), django.core.validators.MaxLengthValidator(12)])),
                ('dob', models.DateField(help_text='Date of birth as per Aadhaar')),
                ('age_at_application', models.PositiveSmallIntegerField(blank=True, help_text='Age at the time of application (auto-calculated)', null=True)),
                # UID Photo Links
                ('uid_front_link', models.URLField(blank=True, help_text='URL to Aadhaar/UID front photo (compressed)', max_length=500, null=True)),
                ('uid_back_link', models.URLField(blank=True, help_text='URL to Aadhaar/UID back photo (compressed)', max_length=500, null=True)),
                ('uid_original_front_link', models.URLField(blank=True, help_text='URL to original uncompressed Aadhaar/UID front photo', max_length=500, null=True)),
                ('uid_original_back_link', models.URLField(blank=True, help_text='URL to original uncompressed Aadhaar/UID back photo', max_length=500, null=True)),
                # OCR Processing Results
                ('uid_check_result', models.JSONField(blank=True, help_text='OCR results from Zoho Catalyst containing extracted Aadhaar data (name, DOB, gender, address, etc.)', null=True)),
                ('is_valid_uid', models.BooleanField(default=False, help_text='Whether UID/Aadhaar validation passed')),
                ('validated', models.BooleanField(default=False, help_text='Whether family member data has been validated')),
                # File Metadata
                ('uid_front_compressed', models.BooleanField(default=False, help_text='Whether front UID photo has been compressed')),
                ('uid_back_compressed', models.BooleanField(default=False, help_text='Whether back UID photo has been compressed')),
                ('uid_front_file_size', models.CharField(blank=True, help_text='File size of front UID photo (e.g., "1.2 MB")', max_length=50, null=True)),
                ('uid_back_file_size', models.CharField(blank=True, help_text='File size of back UID photo (e.g., "1.5 MB")', max_length=50, null=True)),
                # Additional Details
                ('additional_details', models.JSONField(blank=True, help_text='Additional details like profession, company name, etc.', null=True)),
                ('ration_card_available', models.BooleanField(default=False, help_text='Whether family member has ration card')),
                ('application', models.ForeignKey(help_text='Related application', on_delete=django.db.models.deletion.CASCADE, related_name='family_members', to='ujjwala_v3.ujjwalav3application')),
            ],
            options={
                'verbose_name': 'Ujjwala V3 Family Member',
                'verbose_name_plural': 'Ujjwala V3 Family Members',
                'db_table': 'ujjwala_v3_family_member',
                'ordering': ['relation_to_applicant', 'dob'],
                'indexes': [
                    models.Index(fields=['application', 'relation_to_applicant'], name='ujjwala_v3_fm_app_rel_idx'),
                    models.Index(fields=['aadhaar_number'], name='ujjwala_v3_fm_aadhaar_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='UjjwalaV3Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('doc_type', models.CharField(choices=[('AADHAAR_FRONT', 'Aadhaar Front'), ('AADHAAR_BACK', 'Aadhaar Back'), ('AADHAAR_XML', 'Aadhaar XML (DigiLocker)'), ('CURRENT_ADDRESS_POA', 'Current Address Proof of Address'), ('PERMANENT_ADDRESS_POA', 'Permanent Address Proof of Address'), ('FAMILY_COMPOSITION_DOC', 'Family Composition / Ration Card'), ('MIGRANT_DECLARATION', 'Migrant Declaration (Annexure-I)'), ('DEPRIVATION_DECLARATION', 'Deprivation Declaration'), ('BANK_PROOF', 'Bank Proof (Passbook/Statement/Cheque)'), ('BANK_PASSBOOK', 'Bank Passbook Copy'), ('CANCELLED_CHEQUE', 'Cancelled Cheque'), ('APPLICANT_PHOTO', 'Applicant Photograph'), ('FAMILY_PHOTO', 'Family Photograph'), ('KITCHEN_PHOTO', 'Kitchen Photograph'), ('LPG_INSTALLATION_AREA_PHOTO', 'LPG Installation Area Photo'), ('APPLICANT_SIGNATURE', 'Applicant Signature'), ('IDENTITY_PROOF', 'Identity Proof'), ('CASTE_CERTIFICATE', 'Caste Certificate'), ('INCOME_CERTIFICATE', 'Income Certificate'), ('OTHER', 'Other Supporting Document')], db_index=True, help_text='Type of document', max_length=50)),
                ('file_url', models.URLField(help_text='URL to uploaded document file (from TUS or other upload service)', max_length=500)),
                ('file_name', models.CharField(help_text='Original file name', max_length=255)),
                ('file_size', models.PositiveBigIntegerField(blank=True, help_text='File size in bytes', null=True)),
                ('mime_type', models.CharField(blank=True, help_text='MIME type of the file', max_length=100, null=True)),
                ('description', models.TextField(blank=True, help_text='Additional description or notes', null=True)),
                ('is_verified', models.BooleanField(default=False, help_text='Whether document has been verified')),
                ('verified_at', models.DateTimeField(blank=True, help_text='Timestamp when document was verified', null=True)),
                ('address', models.ForeignKey(blank=True, help_text='Related address (for address-specific POA documents)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='ujjwala_v3.ujjwalav3address')),
                ('application', models.ForeignKey(help_text='Related application', on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='ujjwala_v3.ujjwalav3application')),
                ('family_member', models.ForeignKey(blank=True, help_text='Related family member (for member-specific documents)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='ujjwala_v3.ujjwalav3familymember')),
                ('uploaded_by', models.ForeignKey(blank=True, help_text='User who uploaded the document', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uploaded_ujjwala_v3_documents', to=settings.AUTH_USER_MODEL)),
                ('verified_by', models.ForeignKey(blank=True, help_text='User who verified the document', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='verified_ujjwala_v3_documents', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Ujjwala V3 Document',
                'verbose_name_plural': 'Ujjwala V3 Documents',
                'db_table': 'ujjwala_v3_document',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['application', 'doc_type'], name='ujjwala_v3_doc_app_type_idx'),
                    models.Index(fields=['family_member', 'doc_type'], name='ujjwala_v3_doc_fm_type_idx'),
                    models.Index(fields=['address', 'doc_type'], name='ujjwala_v3_doc_addr_type_idx'),
                    models.Index(fields=['is_verified', 'doc_type'], name='ujjwala_v3_doc_verified_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='UjjwalaV3AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True, db_index=True)),
                ('action', models.CharField(db_index=True, help_text='Action performed (e.g., CREATED, UPDATED, SUBMITTED, APPROVED)', max_length=100)),
                ('changes', models.JSONField(blank=True, help_text='JSON object containing field changes', null=True)),
                ('remarks', models.TextField(blank=True, help_text='Additional remarks or notes', null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, help_text='IP address of the actor', null=True)),
                ('actor', models.ForeignKey(blank=True, help_text='User who performed the action', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ujjwala_v3_audit_actions', to=settings.AUTH_USER_MODEL)),
                ('application', models.ForeignKey(help_text='Related application', on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='ujjwala_v3.ujjwalav3application')),
            ],
            options={
                'verbose_name': 'Ujjwala V3 Audit Log',
                'verbose_name_plural': 'Ujjwala V3 Audit Logs',
                'db_table': 'ujjwala_v3_audit_log',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['application', 'action', '-created_at'], name='ujjwala_v3_audit_app_act_idx'),
                    models.Index(fields=['actor', '-created_at'], name='ujjwala_v3_audit_actor_idx'),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name='ujjwalav3application',
            constraint=models.CheckConstraint(check=models.Q(applicant_gender='F'), name='ujjwala_v3_applicant_must_be_female'),
        ),
        migrations.AddConstraint(
            model_name='ujjwalav3application',
            constraint=models.CheckConstraint(check=models.Q(is_migrant=True), name='ujjwala_v3_must_be_migrant'),
        ),
        migrations.AddConstraint(
            model_name='ujjwalav3address',
            constraint=models.UniqueConstraint(fields=('application', 'address_type'), name='unique_address_type_per_application'),
        ),
        migrations.AddConstraint(
            model_name='ujjwalav3familymember',
            constraint=models.UniqueConstraint(condition=models.Q(relation_to_applicant='SELF'), fields=('application', 'relation_to_applicant'), name='unique_self_member_per_application'),
        ),
    ]
