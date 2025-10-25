# Database Schema Guide

## 📋 Schema Execution Order

**IMPORTANT**: The schema files must be executed in this specific order:

1. **`00_enums.sql`** - Database enums (MUST BE FIRST)
2. `01_users.sql` - Users table and auth triggers
3. `02_brands.sql` - Food brands table
4. `03_meals.sql` - Meals/food items table
5. `04_images.sql` - Image uploads and AI analysis
6. `05_logs.sql` - User meal consumption logs
7. `06_user_preferences.sql` - User app preferences and settings

## 🔧 Database Enums

All schemas now use database enums instead of text constraints for better type safety and performance. The enums are defined in `00_enums.sql` and include:

### User-related enums:
- `gender_type`: male, female, other
- `activity_level_type`: sedentary, light, moderate, active, very_active  
- `goal_type`: lose, maintain, gain

### Meal-related enums:
- `meal_type`: breakfast, lunch, dinner, snack, drink, dessert
- `serving_unit_type`: g, ml, oz, cup, piece, slice, tbsp, tsp
- `food_category_type`: fruits, vegetables, grains, protein, dairy, fats, beverages, sweets, processed

### Brand-related enums:
- `brand_category_type`: restaurant, packaged_food, beverage, supplement, organic, fast_food

### Image-related enums:
- `mime_type`: image/jpeg, image/png, image/webp, image/heic
- `ai_processing_status_type`: pending, processing, completed, failed
- `image_type`: meal_photo, ingredient_photo, nutrition_label, receipt  
- `moderation_status_type`: pending, approved, rejected

### Logging enums:
- `logging_method_type`: manual, barcode, photo, voice

### User preference enums:
- `units_system_type`: metric, imperial
- `date_format_type`: MM/DD/YYYY, DD/MM/YYYY, YYYY-MM-DD
- `time_format_type`: 12h, 24h
- `theme_preference_type`: light, dark, system

---

# Table Design Guide: `users` vs `user_preferences`

## 📊 Table Purpose Overview

### `users` - Core Identity & Profile
**What it contains:** Stable, essential data needed for app functionality and identity

### `user_preferences` - Settings & Customizations  
**What it contains:** Changeable settings and personal preferences for app behavior

---

## 🔒 Security & Row Level Security (RLS)

### **Service Roles & Permissions:**

| Role | Purpose | Permissions | RLS Bypass |
|------|---------|-------------|------------|
| `service_role` | Admin operations, data seeding | ALL (SELECT, INSERT, UPDATE, DELETE) | ✅ Yes (bypasses RLS) |
| `authenticated` | Regular app users | Limited per table | ❌ No (respects RLS) |
| `supabase_auth_admin` | Auth triggers only | INSERT on users table | ❌ No |

### **RLS Policies by Table:**

#### **`users` Table:**
- **SELECT**: Public (all users visible to everyone)
- **INSERT**: Users can only insert their own record (`auth.uid() = id`)
- **UPDATE**: Users can only update their own record (`auth.uid() = id`)
- **DELETE**: Not allowed for regular users

#### **`user_preferences` Table:**
- **SELECT**: Users can only view their own preferences (`auth.uid() = user_id`)
- **INSERT**: Users can only insert their own preferences (`auth.uid() = user_id`)
- **UPDATE**: Users can only update their own preferences (`auth.uid() = user_id`)
- **DELETE**: Users can only delete their own preferences (`auth.uid() = user_id`)

#### **`meals` Table:**
- **SELECT**: All active meals visible to everyone (`is_active = true`)
- **INSERT**: Authenticated users can create meals
- **UPDATE**: Users can only update meals they created (`created_by = auth.uid()`)
- **DELETE**: Users can only delete meals they created (`created_by = auth.uid()`)

#### **`logs` Table:**
- **SELECT**: Users can only view their own logs (`auth.uid() = user_id`)
- **INSERT**: Users can only insert their own logs (`auth.uid() = user_id`)
- **UPDATE**: Users can only update their own logs (`auth.uid() = user_id`)
- **DELETE**: Users can only delete their own logs (`auth.uid() = user_id`)

#### **`images` Table:**
- **SELECT**: Users can view public images OR their own images
- **INSERT**: Users can only upload as themselves (`auth.uid() = uploaded_by`)
- **UPDATE**: Users can only update their own images (`auth.uid() = uploaded_by`)
- **DELETE**: Users can only delete their own images (`auth.uid() = uploaded_by`)

#### **`brands` Table:**
- **SELECT**: All active brands visible to everyone (`is_active = true`)
- **INSERT**: Authenticated users can create brands
- **UPDATE**: Authenticated users can update brands (community-driven)

### **🛡️ Data Protection Features:**

1. **User Data Isolation**: Each user can only access their own personal data (logs, preferences, images)
2. **Public Data Sharing**: Profile info and meals are public for social features
3. **Admin Operations**: Service role can perform bulk operations for seeding/maintenance
4. **Trigger Security**: Auth triggers use `SECURITY DEFINER` with minimal permissions

---

## 🏗️ Detailed Breakdown

### 📝 `users` Table - **"WHO you are"**

| Category | Fields | Purpose | Changes |
|----------|--------|---------|---------|
| **Identity** | `username`, `first_name`, `last_name`, `avatar_url`, `website` | Public profile info | Rarely |
| **Physical Data** | `age`, `gender`, `height_cm`, `current_weight_kg` | Calorie calculations | Occasionally |
| **Health Goals** | `activity_level`, `goal_type`, `target_weight_kg`, `daily_calorie_goal` | Core app functionality | Sometimes |
| **Account Status** | `is_active`, `onboarding_completed` | Account management | Rarely |

**Example Usage:**
```sql
-- Get user profile for display
SELECT username, first_name, last_name, avatar_url FROM users WHERE id = $1;

-- Calculate daily calories needed
SELECT age, gender, height_cm, current_weight_kg, activity_level FROM users WHERE id = $1;
```

---

### ⚙️ `user_preferences` Table - **"HOW you want the app to work"**

| Category | Fields | Purpose | Changes |
|----------|--------|---------|---------|
| **Display** | `timezone`, `units_system`, `theme_preference`, `date_format` | UI appearance | Frequently |
| **App Behavior** | `enable_barcode_scanning`, `auto_log_favorites`, `enable_photo_analysis` | Feature toggles | Frequently |
| **Tracking** | `track_macros`, `track_water`, `daily_water_goal_ml` | What to monitor | Sometimes |
| **Dietary** | `dietary_restrictions`, `allergies`, `preferred_cuisines` | Food preferences | Occasionally |
| **Notifications** | `enable_meal_reminders`, `breakfast_reminder_time` | When to notify | Frequently |
| **Privacy** | `make_profile_public`, `share_achievements` | Sharing settings | Sometimes |

**Example Usage:**
```sql
-- Load user's app settings
SELECT timezone, units_system, theme_preference FROM user_preferences WHERE user_id = $1;

-- Check notification preferences
SELECT enable_meal_reminders, breakfast_reminder_time FROM user_preferences WHERE user_id = $1;
```

---

## 🤔 Decision Guide: Which Table?

### Put in `users` if the data is:
- ✅ **Essential** for app core functionality
- ✅ **Stable** - changes rarely
- ✅ **Identity-related** - who the person is
- ✅ **Potentially public** - might be visible to others

### Put in `user_preferences` if the data is:
- ✅ **Customization** - how they want the app to work
- ✅ **Changeable** - user adjusts frequently
- ✅ **Behavioral** - app feature settings
- ✅ **Private** - personal preferences only

---

## 💡 Examples

### ❌ Wrong Placement
```sql
-- DON'T put settings in users table
users.theme_preference  -- This is a preference, not identity!
users.enable_notifications  -- This is a setting, not core data!

-- DON'T put core identity in preferences
user_preferences.full_name  -- This is identity, not a preference!
user_preferences.age  -- This is needed for calorie calculations!
```

### ✅ Correct Placement
```sql
-- Core identity and calculation data
users.first_name, users.age, users.height_cm  -- WHO they are
users.daily_calorie_goal  -- WHAT they need (core functionality)

-- Personal preferences and settings
user_preferences.theme_preference  -- HOW they want UI to look
user_preferences.enable_notifications  -- WHEN they want alerts
user_preferences.dietary_restrictions  -- WHAT they prefer to eat
```

---

## 🔄 Relationship

- **One-to-One**: Each `users` record has exactly one `user_preferences` record
- **Auto-created**: `user_preferences` is automatically created when a user signs up
- **Foreign Key**: `user_preferences.user_id` → `users.id`
- **Cascade Delete**: Deleting a user also deletes their preferences

This separation keeps your database clean, queries fast, and makes the codebase easier to understand! 