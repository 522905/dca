from django.test import TestCase

from django.test import TestCase

from communication_log.jobs import move_files_to_minio_processing
from connection_app.enums import ApplicationTypeEnum, ItemCodeEnum, ConnectionTypeEnum, \
	ConnectionApplicationDocumentsEnum
from connection_app.models import ConnectionApplication


class ConnectionApplicationTestCase(TestCase):
    def setUp(self):
        obj = ConnectionApplication.objects.create(
	        name="Ankita",
	        mobile="9780190831",
	        application_type=ApplicationTypeEnum.BLUE_BOOK,
	        item_code=ItemCodeEnum.FC14,
            connection_type=ConnectionTypeEnum.DOUBLE,
	        consumer_id="9999999"
        )
        obj.documents.create(
	        type=ConnectionApplicationDocumentsEnum.UID_FRONT,
	        link="https://tusd.tusdemo.net/files/e12bacee831bbcca9ea35b0bc3739466+HAhCMeJoJ5iuOPR06lH0hFgglmNI_yNjVHaydXZQr_oHuytnr0rcZwoMP3oy3RYqtJS3lHZA1__bZ_6P4OcN1XnGbaLPS5_r5_UhZjDcvr3J_lydo1E_CrLfTOg_ww.M"
        )
        obj.documents.create(
	        type=ConnectionApplicationDocumentsEnum.UID_BACK,
	        link="https://tusd.tusdemo.net/files/e12bacee831bbcca9ea35b0bc3739466+HAhCMeJoJ5iuOPR06lH0hFgglmNI_yNjVHaydXZQr_oHuytnr0rcZwoMP3oy3RYqtJS3lHZA1__bZ_6P4OcN1XnGbaLPS5_r5_UhZjDcvr3J_lydo1E_CrLfTOg_ww.M"
        )

    def test_file_transfer(self):
	    obj = ConnectionApplication.objects.get(consumer_id="9999999")
	    move_files_to_minio_processing(obj.id)
