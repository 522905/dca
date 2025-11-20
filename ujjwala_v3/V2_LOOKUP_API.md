# Ujjwala V2 Application Lookup API

## Overview
This API allows searching for Ujjwala V2 applications by phone number. It returns applications that are in either `NIC_CLEARED` or `READY_FOR_DISBURSEMENT` status.

## Endpoint

**URL:** `/api/ujjwala-v3/v2-lookup/search-by-phone/`

**Method:** `GET`

**Authentication:** Not required (AllowAny)

## Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| phone_number | string | Yes | 10-digit mobile number |

## Request Example

```bash
# Using curl
curl -X GET "http://localhost:8000/api/ujjwala-v3/v2-lookup/search-by-phone/?phone_number=9876543210"

# Using httpie
http GET "http://localhost:8000/api/ujjwala-v3/v2-lookup/search-by-phone/?phone_number=9876543210"
```

## Response Examples

### Success Response (Applications Found)

**Status Code:** `200 OK`

```json
{
    "message": "Found 2 application(s)",
    "phone_number": "9876543210",
    "count": 2,
    "results": [
        {
            "id": 123,
            "name": "Jane Doe",
            "contact_mobile": "9876543210",
            "status": "NIC_CLEARED",
            "consumer_id": "ABC123456",
            "uid_linked_mobile": "9876543210",
            "marital_status": "MARRIED",
            "address": "123 Main St, City",
            "address_json": {
                "house": "123",
                "street": "Main St",
                "city": "City Name",
                "state": "State Name",
                "pincode": "123456"
            },
            "ration_card_number": "RAT123456",
            "ifsc_code": "SBIN0001234",
            "bank_account_number": "1234567890",
            "product": "UJJWALA_14_KG",
            "latitude": "28.6139",
            "longitude": "77.2090",
            "created_on": "2024-01-15T10:30:00Z",
            "updated_on": "2024-01-20T14:45:00Z",
            "documents": [
                {
                    "id": 456,
                    "document_type": "CUSTOMER_PHOTO",
                    "file": "/media/documents/photo.jpg",
                    "created_at": "2024-01-15T10:35:00Z"
                }
            ],
            "family_members": [
                {
                    "id": 789,
                    "name": "John Doe",
                    "relation": "HUSBAND",
                    "uid": "123456789012",
                    "age": 35
                }
            ]
        },
        {
            "id": 124,
            "name": "Jane Doe",
            "contact_mobile": "9876543210",
            "status": "READY_FOR_DISBURSEMENT",
            // ... other fields
        }
    ]
}
```

### Not Found Response

**Status Code:** `404 NOT FOUND`

```json
{
    "message": "No applications found with the given phone number in NIC_CLEARED or READY_FOR_DISBURSEMENT status",
    "phone_number": "9876543210",
    "results": []
}
```

### Error Responses

#### Missing Phone Number

**Status Code:** `400 BAD REQUEST`

```json
{
    "error": "phone_number query parameter is required"
}
```

#### Invalid Phone Number Format

**Status Code:** `400 BAD REQUEST`

```json
{
    "error": "phone_number must be a 10-digit number"
}
```

## Validation Rules

1. **Phone Number Required**: The `phone_number` query parameter must be provided
2. **Format Validation**: Phone number must be exactly 10 digits
3. **Numeric Only**: Phone number must contain only numeric characters
4. **Status Filter**: Only returns applications with status:
   - `NIC_CLEARED`
   - `READY_FOR_DISBURSEMENT`

## Returned Fields

The API returns the complete application data including:

- **Basic Information**: name, contact_mobile, consumer_id, status
- **Personal Details**: marital_status, residential_status, ration_card_number
- **Address Information**: address (text), address_json (structured)
- **Bank Details**: ifsc_code, bank_account_number
- **Product Information**: product (LPG type)
- **Location**: latitude, longitude, accuracy
- **Timestamps**: created_on, updated_on, various verification dates
- **Related Data**:
  - `documents`: All uploaded documents with metadata
  - `family_members`: Family member details with UID information

## Use Cases

1. **Customer Verification**: Verify customer details before disbursement
2. **Status Check**: Check if a customer's application is ready for processing
3. **Data Retrieval**: Get complete application information for further processing
4. **Mobile App Integration**: Allow customers to check their application status

## Implementation Details

- **Location**: `/home/user/dca/ujjwala_v3/viewsets.py:503`
- **ViewSet**: `UjjwalaV2LookupViewSet`
- **Action**: `search_by_phone`
- **Model**: `ujjwala.models.UjjwalaV2Application`
- **Serializer**: `ujjwala.serializers.UjjwalaV2ApplicationSerializer`

## Notes

- The API uses `prefetch_related` to optimize database queries for documents and family members
- Multiple applications can be returned if the same phone number is used across different applications
- The serializer returns all fields (`fields = '__all__'`) from the V2 Application model
- No authentication is required for this endpoint (can be changed by modifying `permission_classes`)

## Future Enhancements

Potential improvements that could be added:

1. Add pagination for large result sets
2. Add filtering by specific status only
3. Add date range filtering
4. Add sorting options
5. Add authentication/authorization if needed
6. Add rate limiting to prevent abuse
7. Add caching for frequently searched phone numbers
