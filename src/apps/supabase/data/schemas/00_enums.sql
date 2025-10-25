-- Database Enums for the Application
-- This file must be executed first before other schema files

-- User-related enums
create type public.gender_type as enum ('male', 'female', 'other');
create type public.activity_level_type as enum ('sedentary', 'light', 'moderate', 'active', 'very_active');
create type public.goal_type as enum ('lose', 'maintain', 'gain');

-- Brand-related enums
create type public.brand_category_type as enum ('restaurant', 'packaged_food', 'beverage', 'supplement', 'organic', 'fast_food');

-- Meal-related enums
create type public.meal_type as enum ('breakfast', 'lunch', 'dinner', 'snack', 'drink', 'dessert');
create type public.serving_unit_type as enum ('g', 'ml', 'oz', 'cup', 'piece', 'slice', 'tbsp', 'tsp');
create type public.food_category_type as enum ('fruits', 'vegetables', 'grains', 'protein', 'dairy', 'fats', 'beverages', 'sweets', 'processed');

-- Image-related enums
create type public.mime_type as enum ('image/jpeg', 'image/png', 'image/webp', 'image/heic');
create type public.ai_processing_status_type as enum ('pending', 'processing', 'completed', 'failed');
create type public.image_type as enum ('meal_photo', 'ingredient_photo', 'nutrition_label', 'receipt');
create type public.moderation_status_type as enum ('pending', 'approved', 'rejected');

-- Log-related enums
create type public.logging_method_type as enum ('manual', 'barcode', 'photo', 'voice');

-- User preferences enums
create type public.units_system_type as enum ('metric', 'imperial');
create type public.date_format_type as enum ('MM/DD/YYYY', 'DD/MM/YYYY', 'YYYY-MM-DD');
create type public.time_format_type as enum ('12h', '24h');
create type public.theme_preference_type as enum ('light', 'dark', 'system'); 