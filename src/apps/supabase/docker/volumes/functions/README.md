# Supabase Edge Functions

This directory contains Edge Functions for the food tracking application. These functions provide core functionality for meal logging, nutrition tracking, and user analytics. All endpoints are publicly accessible and require no authentication.

## Available Functions

### 1. logMeal

Creates a new meal and logs it for a user.

**Endpoint:** `/logMeal`  
**Method:** `POST`  
**Authentication:** Not required

**Request Body:**
```json
{
  "user_id": "string",
  "logged_at": "2024-03-20T12:00:00Z",
  "meal_type": "breakfast|lunch|dinner|snack|drink|dessert",
  "serving_size": 1.0,
  "serving_unit": "g|ml|oz|cup|piece|slice|tbsp|tsp",
  "calories": 500,
  "protein_g": 20,
  "carbs_g": 60,
  "fat_g": 15,
  "notes": "string (optional)",
  "image_id": "string (optional)",
  "is_favorite": false
}
```

**Response:**
```json
{
  "data": {
    "meal": {
      "id": "string",
      "name": "string",
      "meal_type": "string",
      "calories_per_serving": 500,
      "serving_size": 1.0,
      "serving_unit": "string",
      "protein_g": 20,
      "carbs_g": 60,
      "fat_g": 15,
      "created_by": "string"
    },
    "log": {
      "id": "string",
      "meal_id": "string",
      "user_id": "string",
      "logged_date": "2024-03-20",
      "logged_time": "12:00:00",
      "meal_type": "string",
      "portion_consumed": 1.0,
      "calories_consumed": 500,
      "protein_consumed_g": 20,
      "carbs_consumed_g": 60,
      "fat_consumed_g": 15,
      "notes": "string",
      "image_id": "string",
      "is_favorite": false,
      "logging_method": "manual"
    }
  },
  "status": 201
}
```

### 2. getDailySummary

Retrieves nutrition summaries for a date range, with daily breakdowns and total summary.

**Endpoint:** `/getDailySummary`  
**Method:** `GET`  
**Authentication:** Not required

**Query Parameters:**
- `start_date`: Start date in YYYY-MM-DD format (optional, defaults to 1 month ago)
- `end_date`: End date in YYYY-MM-DD format (optional, defaults to today)
- `user_id`: User UUID (optional, randomly selects a user if not provided)

**Response:**
```json
{
  "data": {
    "user_id": "string",
    "date_range": {
      "start": "2024-03-01",
      "end": "2024-03-20"
    },
    "daily_summaries": {
      "2024-03-01": {
        "total_calories": 2000,
        "total_protein_g": 80,
        "total_carbs_g": 250,
        "total_fat_g": 70,
        "meal_count": 4,
        "meals_by_type": {
          "breakfast": 1,
          "lunch": 1,
          "dinner": 1,
          "snack": 1
        }
      },
      // ... other days
    },
    "total_summary": {
      "total_calories": 40000,
      "total_protein_g": 1600,
      "total_carbs_g": 5000,
      "total_fat_g": 1400,
      "meal_count": 80,
      "meals_by_type": {
        "breakfast": 20,
        "lunch": 20,
        "dinner": 20,
        "snack": 20
      }
    }
  },
  "status": 200
}
```

### 3. getDailyActiveUsers

Returns statistics about active users for a specific date.

**Endpoint:** `/getDailyActiveUsers`  
**Method:** `GET`  
**Authentication:** Not required

**Query Parameters:**
- `date`: Date in YYYY-MM-DD format
- `include_details`: Boolean (optional) - Include detailed user information

**Response:**
```json
{
  "data": {
    "count": 150,
    "users": [
      {
        "id": "string",
        "username": "string",
        "meal_count": 3
      }
    ]
  },
  "status": 200
}
```

### 4. getLoggedMealsByDate

Retrieves meal logs for a specific date, with optional user filtering and pagination.

**Endpoint:** `/getLoggedMealsByDate`  
**Method:** `GET`  
**Authentication:** Not required

**Query Parameters:**
- `date`: Date in YYYY-MM-DD format
- `user_id`: User UUID (optional)
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 10, max: 100)

**Response:**
```json
{
  "data": {
    "meals": [
      {
        "id": "string",
        "meal": {
          "name": "string",
          "description": "string",
          "image_url": "string"
        },
        "user": {
          "username": "string"
        },
        // ... other meal log fields
      }
    ],
    "total": 45
  },
  "status": 200
}
```

## Error Responses

All functions return standardized error responses:

```json
{
  "error": "Error message",
  "status": 400|404|500
}
```

Common error codes:
- `400`: Bad Request (invalid parameters)
- `404`: Not Found
- `500`: Internal Server Error



## Testing

Use tools like Thunder Client, Postman, or curl to test the endpoints. Example curl commands:

#### 1. Log a Meal
```bash
curl -X POST 'http://localhost:8000/functions/v1/main/logMeal' \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
    "logged_at": "2025-07-03T12:00:00Z",
    "meal_type": "lunch",
    "serving_size": 1.5,
    "serving_unit": "cup",
    "calories": 450,
    "protein_g": 25,
    "carbs_g": 45,
    "fat_g": 15,
    "notes": "Added extra cheese",
    "is_favorite": false
  }'
```

#### 2. Get Daily Summary
```bash
# Get summary for specific date range and user
curl 'http://localhost:8000/functions/v1/main/getDailySummary?start_date=2025-07-01&end_date=2025-07-03&user_id=d290f1ee-6c54-4b01-90e6-d701748f0851'

# Get summary for last month (default) for random user
curl 'http://localhost:8000/functions/v1/main/getDailySummary'
```

#### 3. Get Daily Active Users
```bash
# Get active users for specific date with details
curl 'http://localhost:8000/functions/v1/main/getDailyActiveUsers?date=2025-07-03&include_details=true'

# Get active users count for today
curl 'http://localhost:8000/functions/v1/main/getDailyActiveUsers'
```

#### 4. Get Logged Meals by Date
```bash
# Get all meals for a specific date
curl 'http://localhost:8000/functions/v1/main/getLoggedMealsByDate?date=2025-07-03'

# Get meals for specific user with pagination
curl 'http://localhost:8000/functions/v1/main/getLoggedMealsByDate?date=2025-07-03&user_id=d290f1ee-6c54-4b01-90e6-d701748f0851&page=1&limit=20'
```

Note: Replace the example UUIDs (`meal_id` and `user_id`) with actual UUIDs from your database.
