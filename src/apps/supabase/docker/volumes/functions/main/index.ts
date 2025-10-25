import { serve } from 'https://deno.land/std@0.131.0/http/server.ts'
import { logMeal } from './logMeal.ts'
import { getDailySummary } from './getDailySummary.ts'
import { getDailyActiveUsers } from './getDailyActiveUsers.ts'
import { getLoggedMealsByDate } from './getLoggedMealsByDate.ts'
import { createResponse } from './types.ts'

console.log('main function started')

serve(async (req: Request) => {
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
      }
    })
  }

  // Parse URL and get function name
  const url = new URL(req.url)
  const functionName = url.pathname.split('/').pop()

  // Route request to appropriate function
  try {
    switch (functionName) {
      case 'logMeal':
        return await logMeal(req)
      case 'getDailySummary':
        return await getDailySummary(req)
      case 'getDailyActiveUsers':
        return await getDailyActiveUsers(req)
      case 'getLoggedMealsByDate':
        return await getLoggedMealsByDate(req)
      default:
        return createResponse(null, 404, 'Function not found')
    }
  } catch (error) {
    console.error('Error processing request:', error)
    return createResponse(null, 500, 'Internal server error')
  }
})
