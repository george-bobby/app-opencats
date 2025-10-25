// Shared types for Edge Functions

export interface Meal {
    id?: string;
    name: string;
    meal_type: 'breakfast' | 'lunch' | 'dinner' | 'snack' | 'drink' | 'dessert';
    calories_per_serving: number;
    serving_size: number;
    serving_unit: 'g' | 'ml' | 'oz' | 'cup' | 'piece' | 'slice' | 'tbsp' | 'tsp';
    protein_g: number;
    carbs_g: number;
    fat_g: number;
    brand_id?: string;
    created_by: string;
    food_category?: 'fruits' | 'vegetables' | 'grains' | 'protein' | 'dairy' | 'fats' | 'beverages' | 'sweets' | 'processed';
    cuisine_type?: 'american' | 'italian' | 'chinese' | 'japanese' | 'mexican' | 'indian' | 'mediterranean' | 'thai' | 'french' | 'fusion';
    dietary_tags?: string[];
    description?: string;
    image_url?: string;
    barcode?: string;
}

export interface MealLog {
    id?: string;
    meal_id?: string;  // Optional since we'll create it
    user_id: string;
    logged_at: string;  // Used for input only, will be split into logged_date and logged_time
    logged_date?: string;  // YYYY-MM-DD format
    logged_time?: string;  // HH:MM:SS format
    meal_type: 'breakfast' | 'lunch' | 'dinner' | 'snack' | 'drink' | 'dessert';
    serving_size: number;  // This becomes portion_consumed in the database
    serving_unit: 'g' | 'ml' | 'oz' | 'cup' | 'piece' | 'slice' | 'tbsp' | 'tsp';
    calories: number;  // Used for meal creation only
    protein_g: number;  // Used for meal creation only
    carbs_g: number;  // Used for meal creation only
    fat_g: number;  // Used for meal creation only
    notes?: string;
    image_id?: string;
    is_favorite?: boolean;
    logging_method?: 'manual' | 'barcode' | 'photo' | 'voice';
}

export interface NutritionSummary {
    total_calories: number;
    total_protein_g: number;
    total_carbs_g: number;
    total_fat_g: number;
    meal_count: number;
    meals_by_type: {
        [key: string]: number;
    };
}

export interface ErrorResponse {
    error: string;
    details?: unknown;
}

export interface SuccessResponse<T> {
    data: T;
    message?: string;
}

export type APIResponse<T> = Response & {
    data?: T;
    error?: ErrorResponse;
}

// Helper function to create a JSON response
export function createResponse<T>(data: T | null, status: number = 200, error?: string): Response {
    const body = error
        ? { error, status }
        : { data, status };

    return new Response(
        JSON.stringify(body),
        {
            status,
            headers: {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            }
        }
    );
}

// Helper function to validate date string
export function isValidDateString(dateStr: string): boolean {
    const date = new Date(dateStr);
    return date instanceof Date && !isNaN(date.getTime());
}

// Helper function to get start and end of day timestamps
export function getDayBounds(dateStr: string): { start: string; end: string } {
    const date = new Date(dateStr);
    const start = new Date(date.setHours(0, 0, 0, 0)).toISOString();
    const end = new Date(date.setHours(23, 59, 59, 999)).toISOString();
    return { start, end };
} 