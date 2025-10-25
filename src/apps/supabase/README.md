# Supabase - Steps to Replicate

## Prerequisites
- Docker and Docker Compose running
- Virtual environment activated: `source .venv/bin/activate`
- OpenAI API key (optional, for AI-powered data generation)

## Setup Process

### 1. Start the container
```bash
python cli.py supabase up
```

### 2. Seed the database
```bash
rm apps/supabase/data/generated/*.json
python cli.py supabase seed
```

### 3. Access Supabase Studio
1. Open `http://localhost:8000` in your browser
2. Login with default credentials:
   - **Username**: `supabase`
   - **Password**: `Admin@123`

### 4. Generate additional test data (optional)
```bash
python cli.py supabase generate --users 300 --brands 300 --meals 3000 --logs 9000
```

## Available Commands
- `up` - Start Supabase services (Studio, Auth, REST API, Storage, etc.)
- `down` - Stop services and cleanup
- `seed` - Create database schema and seed with initial data
- `generate` - Generate additional test data using AI

## Enviroment variables:
If you want to access Supabase via a different URL with domain name, rather than the default `http://localhost:8000`, please also set:
```
SUPABASE_PUBLIC_URL=https://example.com
API_EXTERNAL_URL=https://example.com
```

## Access Points

### Supabase Studio (Dashboard)
- **URL**: http://localhost:3000
- **Username**: `supabase`
- **Password**: `Admin@123`

### API Endpoints
- **REST API**: http://localhost:8000/rest/v1/
- **Auth API**: http://localhost:8000/auth/v1/
- **Storage API**: http://localhost:8000/storage/v1/

### Database Access
- **Host**: localhost
- **Port**: 5432
- **Database**: postgres
- **Username**: postgres.your-tenant-id
- **Password**: your-super-secret-and-long-postgres-password

## Data Structure

This Supabase instance manages a meal tracking application with the following main entities:

### Core Tables
- **users** - User profiles and core identity data
- **user_preferences** - User settings and app preferences
- **brands** - Food brands and manufacturers
- **meals** - Food items and nutritional information
- **images** - User-uploaded meal photos
- **logs** - Meal consumption tracking records

### Authentication
- Built-in Supabase Auth with email/password
- Row Level Security (RLS) enabled for data protection
- Service role for admin operations

### Storage
- Image storage buckets for meal photos
- Automatic image optimization and resizing

## Generated Data Overview

When you run the `seed` command, the following data is created:

- **Users**: Sample user profiles with realistic data
- **Brands**: Food brands and manufacturers
- **Meals**: Comprehensive food database with nutritional info
- **Images**: Sample meal photos with metadata
- **Logs**: Meal consumption history

The `generate` generate data for `seed` with the desired volumes

## Development Features

### Functions
- Custom serverless functions for complex operations
- Located in `docker/volumes/functions/`

## Security Features

### Row Level Security (RLS)
- Users can only access their own data
- Public data (meals, brands) visible to all authenticated users
- Admin service role bypasses RLS for seeding operations

### Authentication Policies
- Email/password authentication
- JWT token-based sessions
- Configurable session expiry

## Database Enums

The application uses PostgreSQL database enums for better type safety and data consistency. All enum types are defined in `00_enums.sql` and must be created before other schema files.

### Schema Execution Order
1. **`00_enums.sql`** - Database enums (MUST BE FIRST)
2. `01_users.sql` - Users table and auth triggers  
3. `02_brands.sql` - Food brands table
4. `03_meals.sql` - Meals/food items table
5. `04_images.sql` - Image uploads and AI analysis
6. `05_logs.sql` - User meal consumption logs
7. `06_user_preferences.sql` - User app preferences and settings

### Available Enums

**User-related:**
- `gender_type`: male, female, other
- `activity_level_type`: sedentary, light, moderate, active, very_active
- `goal_type`: lose, maintain, gain

**Meal-related:**
- `meal_type`: breakfast, lunch, dinner, snack, drink, dessert
- `serving_unit_type`: g, ml, oz, cup, piece, slice, tbsp, tsp
- `food_category_type`: fruits, vegetables, grains, protein, dairy, fats, beverages, sweets, processed

**Brand-related:**
- `brand_category_type`: restaurant, packaged_food, beverage, supplement, organic, fast_food

**Image-related:**
- `mime_type`: image/jpeg, image/png, image/webp, image/heic
- `ai_processing_status_type`: pending, processing, completed, failed
- `image_type`: meal_photo, ingredient_photo, nutrition_label, receipt
- `moderation_status_type`: pending, approved, rejected

**Logging-related:**
- `logging_method_type`: manual, barcode, photo, voice

**User preferences:**
- `units_system_type`: metric, imperial
- `date_format_type`: MM/DD/YYYY, DD/MM/YYYY, YYYY-MM-DD
- `time_format_type`: 12h, 24h
- `theme_preference_type`: light, dark, system

### Python Enum Integration

All database enums have corresponding Python enums in `core/enums.py` to ensure type consistency between the database and application code. The Python enums are used throughout the codebase for data generation, validation, and API responses.

**Usage Example:**
```python
from apps.supabase.core.enums import MealType, GenderType

# Generate random enum value
meal_type = faker.random_element(elements=list(MealType))
gender = faker.random_element(elements=get_enum_values(GenderType))
```

# Supabase Functions

 This tool also backfill some Supabase Functions. These functions provide core functionality for meal logging, nutrition tracking, and user analytics. All endpoints are publicly accessible and require no authentication.

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
