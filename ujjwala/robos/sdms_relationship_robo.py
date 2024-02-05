import re

from django.db.models import Q
from django.db.models import Case, When, Value, IntegerField
from django.http import JsonResponse, HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action

from ujjwala.enums import UjjwalaV2ApplicationStatus, RoboSdmsDedeupStatusEnum, PreInspectionStatusEnum, \
	FamilyMemberRelationEnum
from ujjwala.models import UjjwalaV2Application
from ujjwala.ujjwala_functions import get_salutation

#ids=['25095','25106','25107','25109','25112','19707','25119','25123','25126','25128','25137','21625','25140','25154','23053','23014','23060','22934','21831','21843','23277','23289','23299','23320','23323','23317','23331','23336','23340','23342','23347','23348','23351','21306','23356','23355','23358','23365','23367','23359','23360','23366','23363','23372','23375','23377','23374','23381','23384','23391','23395','23362','23404','23423','23410','23424','23428','23432','23449','23476','23421','23271','23485','23487','22616','9694','22495','23503','23499','22029','22050','23515','23517','25163','23553','23562','23572','25167','23590','23599','23601','23616','23622','23624','25177','23635','23644','23636','21570','23650','23655','23657','23659','23660','23664','23671','22040','25202','23679','25205','22085','23694','25220','22172','22178','25227','23724','25232','23735','23734','23746','23755','23749','23752','25247','23760','23767','25250','25251','23773','23776','22280','23780','23781','23789','23790','23785','23786','23788','23797','23794','23799','23798','23802','23805','21529','23831','25275','22430','22439','25288','23851','23852','25282','22549','25293','22568','25296','25297','22282','23804','23868','23869','23870','23801','23651','23885','22701','23757','23640','25307','22726','23796','23774','23730','23770','22747','23731','23716','23722','25313','22802','25314','25317','23638','22321','23646','23894','23484','22867','23926','25328','22904','22833','22662','23931','25336','23934','23939','23942','23941','25340','25345','23948','25349','23951','23953','25364','25366','23959','23969','23972','23973','23974','23975','23980','23981','23982','23983','25381','25383','23992','23987','25387','25404','24002','23999','24001','25395','25396','23238','24012','24016','24015','24013','25422','25409','24021','24025','25405','25426','24040','25444','25450','25452','25460','25455','24065','25464','25473','25474','24063','22670','24075','25468','25465','25461','25458','24078','25502','24085','25504','25433','25488','25525','24644','24638','24095','24096','24099','25519','24100','24105','24109','24554','23896','25596','25586','25547','25605','24133','24710','24139','24088','25611','25577','24152','24157','25623','24177','24168','24169','23482','23777','25413','24192','24199','24224','24219','24213','24223','24229','24237','24242','24248','24249','24253','24261','24264','24276','24277','24279','24286','24287','24289','24231','24294','24298','24301','24308','24309','24310','24304','24317','24326','24336','24332','24347','24354','24355','24357','24362','24368','24375','24383','24385','24398','24401','24402','24411','24449','24417','24454','24476','24484','24495','24496','24500','24524','24527','24535','24542','24621','24627','24637','24642','24649','24592','24660','24667','24669','24695','24702','24707','24715','24711','24740','24832','24859','24929','24866','24932','24900','24904','24937','24910','24879','24941','24957','24951','24954','24950','24944','24955','24946','24959','24956','24998','24995','24996','24921','24891','25003','21499','21502','24976','25029','25070','25071','25033','25034','24977','25076','25077','25041','25042','24978','25049','25050','25090','25053','24979','24980','24981','25062','25065','25067','25069']
ids=['26481']

class UjjwalaApplicationSdmsRelationshipViewSet(viewsets.ViewSet):
	@action(methods=['get'], detail=False, url_path='get_records_for_new_relationship')
	def get_records_for_new_relationship(self, request, *args, **kwargs):
		record_list = UjjwalaV2Application.objects.filter(
			Q(status=UjjwalaV2ApplicationStatus.DOCUMENTS_UPLOADED)
			& Q(robo_sdms_dedup=RoboSdmsDedeupStatusEnum.PROCESSED_AND_UNIQUE)
                        #& Q(robo_execution_failed_count=0)
			#& Q(pre_inspection__status=PreInspectionStatusEnum.SUBMITTED)
		).filter(
#			filled_by_id__in=[118,110,113,111,119,121,55,142]
		).filter(
			pk__in=ids
		).exclude(
			address_json__isnull=True
		).exclude(
			ifsc_code__isnull=True
		).exclude(
			family_members__uid_no__in=['999999999999', '666666666666', '0', '1']
		).exclude(
			family_members__dob__gte='2004-09-01'
		).exclude(
			robo_execution_failed_count__gt=2
		).annotate(
			custom_order=Case(
				When(pre_inspection__status=PreInspectionStatusEnum.ACCEPTED, then=Value(1)),
				When(pre_inspection__status=PreInspectionStatusEnum.SUBMITTED, then=Value(2)),
				default=Value(3),
				output_field=IntegerField(),
			)
		).order_by("custom_order", "id")

		data = []

		for record in record_list:
			try:
				address = record.get_address_for_sdms_upload()
			except:
				continue


			pi_status = 'NA'
			try:
				pi_status = record.pre_inspection.status
			except:
				pass

			self_fm = record.family_members.get(relation=FamilyMemberRelationEnum.SELF)
			# self_name_split = record.name.split(" ")
			if self_fm.name != record.name:
				record.name = self_fm.name
				record.save()
			self_name_split = self_fm.name.split(" ")

			if self_name_split[0].strip() == '':
				continue

			data.append({
				"id": record.id,
				"First Name": self_name_split[0].title(),
				"Last Name": ' '.join(self_name_split[1:]).title() if len(self_name_split) > 1 else '.',
				"Salutation": get_salutation(self_fm),
				"Gender": "Female",
				"DOB": self_fm.dob,
				"Migrated": "Y",
				"Relationship": "SELF",
				"phone": record.contact_mobile,
				"identities": [{
					"Identity Type": "POA-POI",
					"Identity Method": "Aadhaar(UID)",
					"Identity Num": self_fm.uid_no
				}],
				'consumer_id': record.consumer_id,
				"address": {
					"address": address['addr_str'].strip().replace('\\', '/'),
					"landmark": f'DcaId-{record.id} ' + record.address_json.get('landmark', 'NA'),
					"pincode": address['pincode']
				},
				"bank": {
					"account": record.bank_account_number,
					"ifsc": record.ifsc_code
				},
				"extras": {
					"pi_status": pi_status
				}
			})
		return JsonResponse(data, safe=False)

	@action(methods=['post'], detail=False, url_path='update_new_relationship')
	def update_new_relationship(self, request, *args, **kwargs):
		application = UjjwalaV2Application.objects.get(id=request.data.get('id'))
		uid_check_result = request.data.get('uid_check_result')
		p = re.compile("DcaId-([^\s]+)")
		result = p.search(uid_check_result['contact_address'])

		if result:
			dca_id = result.group(1)
			if not request.data.get('id') == int(dca_id):
				return HttpResponse("Application Id Mis-match")
		else:
			print("Skipping Id Comparison")

		sdms_mobile_number = uid_check_result.get('phone_number', '')
		self_fm = application.family_members.get(relation=FamilyMemberRelationEnum.SELF)
		self_fm.uid_check_result = uid_check_result
		self_fm.save()

		application.sdms_mobile_number = sdms_mobile_number
		application.consumer_id = request.data.get('consumer_id')
		application.manual_operation_code = "ROBO_STARTED_RELATION"

		application.ekyc_accepted_or_rejected(
			sdms_mobile_number=sdms_mobile_number,
			description="Bot Created New Relation"
		)
		application.save()

		return HttpResponse("Ok")
