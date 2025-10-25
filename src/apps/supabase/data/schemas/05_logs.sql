-- Create 'logs' table for tracking user meal consumption
create table public.logs (
  id uuid default gen_random_uuid() primary key,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now(),
  
  -- Relationships
  user_id uuid references public.users(id) on delete cascade not null,
  meal_id uuid references public.meals(id) on delete cascade not null,
  
  -- Consumption details
  logged_date date not null default current_date,
  logged_time time with time zone default current_time,
  portion_consumed numeric(8,2) not null default 1.0 check (portion_consumed > 0),
  
  -- Calculated nutrition (based on portion)
  calories_consumed numeric(8,2) not null check (calories_consumed >= 0),
  protein_consumed_g numeric(6,2) default 0 check (protein_consumed_g >= 0),
  carbs_consumed_g numeric(6,2) default 0 check (carbs_consumed_g >= 0),
  fat_consumed_g numeric(6,2) default 0 check (fat_consumed_g >= 0),
  
  -- Meal context
  meal_type public.meal_type,
  notes text,
  
  -- Location and method
  location text, -- e.g., 'home', 'restaurant', 'office'
  logging_method public.logging_method_type default 'manual',
  
  -- Image reference for this specific log entry
  image_id uuid references public.images(id) on delete set null,
  
  -- Metadata
  is_favorite boolean default false,
  confidence_score numeric(3,2) default 1.0 check (confidence_score >= 0 and confidence_score <= 1.0)
);

-- Set up Row Level Security (RLS)
alter table public.logs enable row level security;

-- Policies for logs table
create policy "Users can view their own logs" on public.logs
  for select using (auth.uid() = user_id);

create policy "Users can insert their own logs" on public.logs
  for insert with check (auth.uid() = user_id);

create policy "Users can update their own logs" on public.logs
  for update using (auth.uid() = user_id);

create policy "Users can delete their own logs" on public.logs
  for delete using (auth.uid() = user_id);

-- Create indexes for better performance
create index idx_logs_user_id on public.logs(user_id);
create index idx_logs_meal_id on public.logs(meal_id);
create index idx_logs_logged_date on public.logs(logged_date desc);
create index idx_logs_user_date on public.logs(user_id, logged_date desc);
create index idx_logs_meal_type on public.logs(meal_type);
create index idx_logs_created_at on public.logs(created_at desc);
create index idx_logs_calories_consumed on public.logs(calories_consumed);

-- Create trigger to update 'updated_at' timestamp
create trigger trigger_logs_updated_at
  before update on public.logs
  for each row execute function public.handle_updated_at();

-- Function to automatically calculate nutrition based on portion and meal data
create or replace function public.calculate_log_nutrition()
returns trigger as $$
begin
  -- Get meal nutrition data and calculate based on portion
  select 
    NEW.portion_consumed * m.calories_per_serving,
    NEW.portion_consumed * m.protein_g,
    NEW.portion_consumed * m.carbs_g,
    NEW.portion_consumed * m.fat_g
  into 
    NEW.calories_consumed,
    NEW.protein_consumed_g,
    NEW.carbs_consumed_g,
    NEW.fat_consumed_g
  from public.meals m
  where m.id = NEW.meal_id;
  
  return NEW;
end;
$$ language plpgsql;

-- Create trigger to auto-calculate nutrition on insert/update
create trigger trigger_logs_calculate_nutrition
  before insert or update on public.logs
  for each row execute function public.calculate_log_nutrition();

-- Create a view for daily nutrition summaries
create or replace view public.daily_nutrition_summary as
select 
  user_id,
  logged_date,
  count(*) as total_entries,
  sum(calories_consumed) as total_calories,
  sum(protein_consumed_g) as total_protein_g,
  sum(carbs_consumed_g) as total_carbs_g,
  sum(fat_consumed_g) as total_fat_g,
  count(case when meal_type = 'breakfast' then 1 end) as breakfast_count,
  count(case when meal_type = 'lunch' then 1 end) as lunch_count,
  count(case when meal_type = 'dinner' then 1 end) as dinner_count,
  count(case when meal_type = 'snack' then 1 end) as snack_count
from public.logs
group by user_id, logged_date
order by user_id, logged_date desc;

-- Grant permissions for Supabase service role (for admin operations)
grant all on table public.logs to service_role;

-- Grant permissions for authenticated users  
grant select, insert, update, delete on table public.logs to authenticated; 