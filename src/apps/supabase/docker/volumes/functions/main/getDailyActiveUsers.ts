import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.39.7'
import { createResponse, isValidDateString, getDayBounds } from './types.ts'

// Initialize Supabase client
const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
const supabase = createClient(supabaseUrl, supabaseKey)

interface DailyActiveUsersResponse {
    count: number;
    users?: Array<{
        id: string;
        username: string;
        meal_count: number;
    }>;
}

export async function getDailyActiveUsers(req: Request): Promise<Response> {
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
        let date = url.searchParams.get('date')
        const includeDetails = url.searchParams.get('include_details') === 'true'

        // If no date provided, use today's date
        if (!date) {
            date = new Date().toISOString().split('T')[0]  // YYYY-MM-DD format
        }
        // Validate date format
        else if (!isValidDateString(date)) {
            return createResponse(null, 400, 'Invalid date format')
        }

        // Get start and end of day timestamps
        const { start, end } = getDayBounds(date)

        if (includeDetails) {
            // First get distinct user_ids and their meal counts
            const { data: logs, error: logsError } = await supabase
                .from('logs')
                .select(`
                    user_id,
                    users!inner (
                        id,
                        username
                    )
                `)
                .eq('logged_date', date)

            if (logsError) {
                console.error('Error fetching logs:', logsError)
                return createResponse(null, 500, 'Failed to fetch logs')
            }

            // Count meals per user
            const userMealCounts = new Map<string, { username: string; count: number }>()
            logs.forEach(log => {
                const userId = log.user_id
                const username = log.users.username
                if (!userMealCounts.has(userId)) {
                    userMealCounts.set(userId, { username, count: 1 })
                } else {
                    userMealCounts.get(userId)!.count++
                }
            })

            // Create final response with user details
            const activeUsers = Array.from(userMealCounts.entries())
                .map(([id, { username, count }]) => ({
                    id,
                    username,
                    meal_count: count
                }))
                .sort((a, b) => b.meal_count - a.meal_count)

            const response: DailyActiveUsersResponse = {
                count: activeUsers.length,
                users: activeUsers
            }

            return createResponse(response)
        } else {
            // Query for just distinct user count, joining with users table to ensure they exist
            const { data: logs, error: logsError } = await supabase
                .from('logs')
                .select(`
                    user_id,
                    users!inner (id)
                `)
                .eq('logged_date', date)

            if (logsError) {
                console.error('Error fetching active users count:', logsError)
                return createResponse(null, 500, 'Failed to fetch active users count')
            }

            // Count unique users that exist in both tables
            const uniqueUserIds = new Set(logs.map(log => log.user_id))

            const response: DailyActiveUsersResponse = {
                count: uniqueUserIds.size
            }

            return createResponse(response)
        }
    } catch (error) {
        console.error('Error processing request:', error)
        return createResponse(null, 500, 'Internal server error')
    }
} 