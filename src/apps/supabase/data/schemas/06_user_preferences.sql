-- Create 'user_preferences' table for app settings and personal preferences
-- This table contains: settings, preferences, and customizations that change frequently
create table public.user_preferences (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.users(id) on delete cascade not null unique,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now(),
  
  -- System & Display Preferences (how the app looks and behaves)
  timezone text default 'UTC',
  units_system public.units_system_type default 'metric',
  preferred_date_format public.date_format_type default 'MM/DD/YYYY',
  preferred_time_format public.time_format_type default '12h',
  theme_preference public.theme_preference_type default 'system',
  
  -- App Behavior Settings (how features work)
  auto_log_favorites boolean default true,
  enable_barcode_scanning boolean default true,
  enable_photo_analysis boolean default true,
  enable_voice_logging boolean default false,
  
  -- Tracking Preferences (what to track)
  track_macros boolean default true,
  track_water boolean default true,
  track_exercise boolean default false,
  daily_water_goal_ml integer default 2000 check (daily_water_goal_ml > 0),
  
  -- Dietary Preferences & Restrictions (personal food choices)
  dietary_restrictions text[] default '{}', -- e.g., 'vegetarian', 'vegan', 'gluten-free', 'dairy-free', 'nut-free'
  allergies text[] default '{}',
  preferred_cuisines text[] default '{}',
  disliked_foods text[] default '{}',
  
  -- Notification Settings (when to be notified)
  enable_meal_reminders boolean default true,
  enable_water_reminders boolean default true,
  enable_goal_notifications boolean default true,
  enable_achievement_notifications boolean default true,
  breakfast_reminder_time time,
  lunch_reminder_time time,
  dinner_reminder_time time,
  water_reminder_interval_minutes integer default 120 check (water_reminder_interval_minutes > 0),
  
  -- Privacy Settings (what to share)
  make_profile_public boolean default false,
  share_achievements boolean default true,
  allow_friend_requests boolean default true,
  
  -- Data Management (backup and retention)
  auto_backup_enabled boolean default true,
  last_backup_date timestamp with time zone,
  data_retention_days integer default 365 check (data_retention_days > 0)
);

-- Set up Row Level Security (RLS)
alter table public.user_preferences enable row level security;

-- Policies for user_preferences table
create policy "Users can view their own preferences" on public.user_preferences
  for select using (auth.uid() = user_id);

create policy "Users can insert their own preferences" on public.user_preferences
  for insert with check (auth.uid() = user_id);

create policy "Users can update their own preferences" on public.user_preferences
  for update using (auth.uid() = user_id);

create policy "Users can delete their own preferences" on public.user_preferences
  for delete using (auth.uid() = user_id);

-- Create indexes for better performance
create unique index idx_user_preferences_user_id on public.user_preferences(user_id);
create index idx_user_preferences_dietary_restrictions on public.user_preferences using gin(dietary_restrictions);
create index idx_user_preferences_allergies on public.user_preferences using gin(allergies);

-- Create trigger to update 'updated_at' timestamp
create trigger trigger_user_preferences_updated_at
  before update on public.user_preferences
  for each row execute function public.handle_updated_at();

-- Function to create default preferences for new users
create or replace function public.create_default_user_preferences()
returns trigger as $$
begin
  insert into public.user_preferences (user_id)
  values (NEW.id)
  on conflict (user_id) do nothing;
  return NEW;
end;
$$ language plpgsql;

-- Create trigger to auto-create preferences when a new user is created
create trigger trigger_create_default_preferences
  after insert on public.users
  for each row execute function public.create_default_user_preferences();

-- Grant permissions for Supabase service role (for admin operations)
grant all on table public.user_preferences to service_role;

-- Grant permissions for authenticated users  
grant select, insert, update, delete on table public.user_preferences to authenticated; 