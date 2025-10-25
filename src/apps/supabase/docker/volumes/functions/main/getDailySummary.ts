import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.39.7'
import { NutritionSummary, createResponse, isValidDateString } from './types.ts'

// Initialize Supabase client
const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
const supabase = createClient(supabaseUrl, supabaseKey)

function getDefaultDateRange(): { start: string; end: string } {
    const end = new Date()
    const start = new Date()
    start.setMonth(start.getMonth() - 1) // Last month
    return {
        start: start.toISOString().split('T')[0], // YYYY-MM-DD format
        end: end.toISOString().split('T')[0]
    }
}

async function getRandomUserId(): Promise<string | null> {
    try {
        // First get the count of users
        const { count, error: countError } = await supabase
            .from('users')
            .select('*', { count: 'exact', head: true })

        if (countError || !count) {
            console.error('Error getting user count:', countError)
            return null
        }

        // Generate a random offset
        const randomOffset = Math.floor(Math.random() * count)

        // Get a random user using OFFSET
        const { data, error } = await supabase
            .from('users')
            .select('id')
            .limit(1)
            .range(randomOffset, randomOffset)
            .single()

        if (error || !data) {
            console.error('Error fetching random user:', error)
            return null
        }

        return data.id
    } catch (error) {
        console.error('Error in getRandomUserId:', error)
        return null
    }
}

export async function getDailySummary(req: Request): Promise<Response> {
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
        let startDate = url.searchParams.get('start_date')
        let endDate = url.searchParams.get('end_date')
        let userId = url.searchParams.get('user_id')

        // If no date range provided, use last month
        if (!startDate || !endDate) {
            const defaultRange = getDefaultDateRange()
            startDate = defaultRange.start
            endDate = defaultRange.end
        }

        // Validate date formats
        if (!isValidDateString(startDate) || !isValidDateString(endDate)) {
            return createResponse(null, 400, 'Invalid date format. Use YYYY-MM-DD')
        }

        // Validate date range
        const start = new Date(startDate)
        const end = new Date(endDate)
        if (start > end) {
            return createResponse(null, 400, 'Start date must be before or equal to end date')
        }

        // If no user_id provided, get a random user
        if (!userId) {
            userId = await getRandomUserId()
            if (!userId) {
                return createResponse(null, 500, 'Failed to get random user')
            }
        }

        // Query meal logs for the specified date range and user
        const { data: mealLogs, error } = await supabase
            .from('logs')
            .select(`
        *,
        meals!meal_id (
          name,
          description
        )
      `)
            .eq('user_id', userId)
            .gte('logged_date', startDate)
            .lte('logged_date', endDate)
            .order('logged_date', { ascending: true })

        if (error) {
            console.error('Error fetching meal logs:', error)
            return createResponse(null, 500, 'Failed to fetch meal logs')
        }

        // Initialize summary with daily breakdowns
        const dailySummaries: { [date: string]: NutritionSummary } = {}
        let totalSummary: NutritionSummary = {
            total_calories: 0,
            total_protein_g: 0,
            total_carbs_g: 0,
            total_fat_g: 0,
            meal_count: 0,
            meals_by_type: {}
        }

        // Process each meal log
        for (const log of mealLogs) {
            const date = log.logged_date

            // Initialize daily summary if not exists
            if (!dailySummaries[date]) {
                dailySummaries[date] = {
                    total_calories: 0,
                    total_protein_g: 0,
                    total_carbs_g: 0,
                    total_fat_g: 0,
                    meal_count: 0,
                    meals_by_type: {}
                }
            }

            // Update daily summary
            dailySummaries[date].total_calories += log.calories_consumed
            dailySummaries[date].total_protein_g += log.protein_consumed_g
            dailySummaries[date].total_carbs_g += log.carbs_consumed_g
            dailySummaries[date].total_fat_g += log.fat_consumed_g
            dailySummaries[date].meal_count += 1
            dailySummaries[date].meals_by_type[log.meal_type] = (dailySummaries[date].meals_by_type[log.meal_type] || 0) + 1

            // Update total summary
            totalSummary.total_calories += log.calories_consumed
            totalSummary.total_protein_g += log.protein_consumed_g
            totalSummary.total_carbs_g += log.carbs_consumed_g
            totalSummary.total_fat_g += log.fat_consumed_g
            totalSummary.meal_count += 1
            totalSummary.meals_by_type[log.meal_type] = (totalSummary.meals_by_type[log.meal_type] || 0) + 1
        }

        // Round numeric values to 2 decimal places in all summaries
        for (const date in dailySummaries) {
            dailySummaries[date].total_protein_g = Number(dailySummaries[date].total_protein_g.toFixed(2))
            dailySummaries[date].total_carbs_g = Number(dailySummaries[date].total_carbs_g.toFixed(2))
            dailySummaries[date].total_fat_g = Number(dailySummaries[date].total_fat_g.toFixed(2))
        }

        totalSummary.total_protein_g = Number(totalSummary.total_protein_g.toFixed(2))
        totalSummary.total_carbs_g = Number(totalSummary.total_carbs_g.toFixed(2))
        totalSummary.total_fat_g = Number(totalSummary.total_fat_g.toFixed(2))

        // Prepare response with both daily breakdown and total summary
        const response = {
            user_id: userId,
            date_range: {
                start: startDate,
                end: endDate
            },
            daily_summaries: dailySummaries,
            total_summary: totalSummary
        }

        return createResponse(response)
    } catch (error) {
        console.error('Error processing request:', error)
        return createResponse(null, 500, 'Internal server error')
    }
} 