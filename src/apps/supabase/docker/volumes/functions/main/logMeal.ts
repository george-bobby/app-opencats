import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.39.7'
import { MealLog, Meal, createResponse } from './types.ts'

// Initialize Supabase client
const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
const supabase = createClient(supabaseUrl, supabaseKey)

export async function logMeal(req: Request): Promise<Response> {
    // Handle preflight requests
    if (req.method === 'OPTIONS') {
        return new Response(null, {
            status: 204,
            headers: {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        })
    }

    // Only allow POST requests
    if (req.method !== 'POST') {
        return createResponse(null, 405, 'Method not allowed')
    }

    try {
        // Parse request body
        const mealLog: MealLog = await req.json()

        // Split logged_at into date and time
        const loggedAt = new Date(mealLog.logged_at)
        const loggedDate = loggedAt.toISOString().split('T')[0]
        const loggedTime = loggedAt.toISOString().split('T')[1].split('.')[0]

        // Validate required fields for meal log
        const requiredFields = ['user_id', 'logged_at', 'meal_type', 'serving_size', 'serving_unit', 'calories', 'protein_g', 'carbs_g', 'fat_g']
        const missingFields = requiredFields.filter(field => !(field in mealLog))

        if (missingFields.length > 0) {
            return createResponse(null, 400, `Missing required fields: ${missingFields.join(', ')}`)
        }

        // Validate numeric fields
        const numericFields = ['serving_size', 'calories', 'protein_g', 'carbs_g', 'fat_g']
        for (const field of numericFields) {
            if (typeof mealLog[field] !== 'number' || mealLog[field] < 0) {
                return createResponse(null, 400, `Invalid value for ${field}: must be a non-negative number`)
            }
        }

        // Validate meal_type
        const validMealTypes = ['breakfast', 'lunch', 'dinner', 'snack', 'drink', 'dessert']
        if (!validMealTypes.includes(mealLog.meal_type)) {
            return createResponse(null, 400, `Invalid meal_type: must be one of ${validMealTypes.join(', ')}`)
        }

        // Validate date format
        const loggedAtDate = new Date(mealLog.logged_at)
        if (isNaN(loggedAtDate.getTime())) {
            return createResponse(null, 400, 'Invalid logged_at date format')
        }

        // Create a new meal record
        const mealData: Meal = {
            name: `${mealLog.meal_type} on ${loggedDate}`,
            meal_type: mealLog.meal_type,
            calories_per_serving: mealLog.calories,
            serving_size: mealLog.serving_size,
            serving_unit: mealLog.serving_unit as Meal['serving_unit'],
            protein_g: mealLog.protein_g,
            carbs_g: mealLog.carbs_g,
            fat_g: mealLog.fat_g,
            created_by: mealLog.user_id
        }

        // Insert new meal into database
        const { data: mealResult, error: mealError } = await supabase
            .from('meals')
            .insert([mealData])
            .select()
            .single()

        if (mealError) {
            console.error('Error creating meal:', mealError)
            return createResponse(null, 500, 'Failed to create meal')
        }

        // Prepare log data with split date and time
        const logData = {
            meal_id: mealResult.id,
            user_id: mealLog.user_id,
            logged_date: loggedDate,
            logged_time: loggedTime,
            meal_type: mealLog.meal_type,
            portion_consumed: mealLog.serving_size,
            notes: mealLog.notes,
            image_id: mealLog.image_id,
            is_favorite: false,
            logging_method: 'manual'
        }

        // Insert meal log into database
        const { data: logResult, error: logError } = await supabase
            .from('logs')
            .insert([logData])
            .select()
            .single()

        if (logError) {
            console.error('Error logging meal:', logError)
            // Try to delete the created meal since logging failed
            await supabase.from('meals').delete().eq('id', mealResult.id)
            return createResponse(null, 500, 'Failed to log meal')
        }

        return createResponse({ meal: mealResult, log: logResult }, 201)
    } catch (error) {
        console.error('Error processing request:', error)
        return createResponse(null, 500, 'Internal server error')
    }
} 