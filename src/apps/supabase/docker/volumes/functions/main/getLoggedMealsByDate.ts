import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.39.7'
import { MealLog, createResponse, isValidDateString, getDayBounds } from './types.ts'

// Initialize Supabase client
const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
const supabase = createClient(supabaseUrl, supabaseKey)

interface LoggedMeal extends MealLog {
    meal: {
        name: string;
        description?: string;
        image_url?: string;
    };
    user: {
        username: string;
    };
}

interface LoggedMealsResponse {
    meals: LoggedMeal[];
    total: number;
}

export async function getLoggedMealsByDate(req: Request): Promise<Response> {
    // Handle preflight requests
    if (req.method === 'OPTIONS') {
        return new Response(null, {
            status: 204,
            headers: {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        })
    }

    // Only allow GET requests
    if (req.method !== 'GET') {
        return createResponse(null, 405, 'Method not allowed')
    }

    try {
        // Get query parameters
        const url = new URL(req.url)
        const date = url.searchParams.get('date')
        const userId = url.searchParams.get('user_id') // Optional: filter by user
        const page = parseInt(url.searchParams.get('page') || '1')
        const limit = parseInt(url.searchParams.get('limit') || '10')

        // Validate date parameter
        if (!date) {
            return createResponse(null, 400, 'Missing required parameter: date')
        }

        // Validate date format
        if (!isValidDateString(date)) {
            return createResponse(null, 400, 'Invalid date format')
        }

        // Validate pagination parameters
        if (isNaN(page) || page < 1 || isNaN(limit) || limit < 1 || limit > 100) {
            return createResponse(null, 400, 'Invalid pagination parameters')
        }

        // Get start and end of day timestamps
        const { start, end } = getDayBounds(date)

        // Build query
        let query = supabase
            .from('logs')
            .select(`
                *,
                meals!inner (
                    name,
                    description,
                    image_url
                ),
                users!inner (
                    username
                )
            `, { count: 'exact' })
            .eq('logged_date', date)
            .order('logged_time', { ascending: false })

        // Add user filter if provided
        if (userId) {
            query = query.eq('user_id', userId)
        }

        // Add pagination
        const offset = (page - 1) * limit
        query = query.range(offset, offset + limit - 1)

        // Execute query
        const { data, error, count } = await query

        if (error) {
            console.error('Error fetching logged meals:', error)
            return createResponse(null, 500, 'Failed to fetch logged meals')
        }

        // Transform response
        const meals = data.map(row => ({
            ...row,
            meal: {
                name: row.meals.name,
                description: row.meals.description,
                image_url: row.meals.image_url
            },
            user: {
                username: row.users.username
            }
        }))

        const response: LoggedMealsResponse = {
            meals,
            total: count || 0
        }

        return createResponse(response)
    } catch (error) {
        console.error('Error processing request:', error)
        return createResponse(null, 500, 'Internal server error')
    }
} 