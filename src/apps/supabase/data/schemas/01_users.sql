-- Create a 'users' table for core user identity and profile information
-- This table contains: identity, profile, and essential data needed for calorie calculations
create table public.users (
  id uuid references auth.users not null primary key,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now(),
  
  -- Core Identity & Profile (visible to others, rarely changes)
  username text unique,
  first_name text,
  last_name text,
  avatar_url text,
  website text,
  
  -- Essential Physical Data (needed for calorie calculations)
  age integer check (age > 0 and age < 150),
  gender public.gender_type,
  height_cm numeric(5,2) check (height_cm > 0),
  current_weight_kg numeric(5,2) check (current_weight_kg > 0),
  
  -- Core Health Goals (fundamental to app functionality)
  activity_level public.activity_level_type default 'moderate',
  goal_type public.goal_type default 'maintain',
  target_weight_kg numeric(5,2) check (target_weight_kg > 0),
  daily_calorie_goal integer check (daily_calorie_goal > 0),
  
  -- Account Status
  is_active boolean default true,
  onboarding_completed boolean default false,
  
  -- Constraints
  constraint username_length check (char_length(username) >= 3)
);

-- Set up Row Level Security (RLS) for 'users' table
alter table public.users enable row level security;

create policy "Public users are viewable by everyone." on public.users
  for select using (true);

create policy "Users can insert their own user record." on public.users
  for insert with check (auth.uid() = id);

create policy "Users can update their own user record." on public.users
  for update using (auth.uid() = id);

-- Create indexes for better performance
create index idx_users_username on public.users(username);
create index idx_users_created_at on public.users(created_at);
create index idx_users_is_active on public.users(is_active);

-- Create trigger to update 'updated_at' timestamp
create or replace function public.handle_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger trigger_users_updated_at
  before update on public.users
  for each row execute function public.handle_updated_at();

-- Function to automatically create public.users record when auth.users record is created
create or replace function public.handle_new_user() 
returns trigger as $$
begin
  insert into public.users (
    id, 
    first_name,
    last_name,
    avatar_url
  )
  values (
    new.id,
    new.raw_user_meta_data->>'first_name',
    new.raw_user_meta_data->>'last_name',
    coalesce(new.raw_user_meta_data->>'avatar_url', new.raw_user_meta_data->>'picture')
  );
  return new;
end;
$$ language plpgsql security definer;

-- Trigger to automatically create public.users record on auth.users insert
create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Grant necessary permissions for the trigger function
grant usage on schema public to supabase_auth_admin;
grant insert on table public.users to supabase_auth_admin;

-- Grant permissions for Supabase service role (for admin operations)
grant all on table public.users to service_role;
grant usage on schema public to service_role;

-- Grant permissions for authenticated users  
grant select, update on table public.users to authenticated;
grant usage on schema public to authenticated;

-- Function to automatically delete public.users record when auth.users record is deleted
create or replace function public.handle_user_deletion() 
returns trigger as $$
begin
  delete from public.users where id = old.id;
  return old;
end;
$$ language plpgsql security definer;

-- Trigger to automatically delete public.users record when auth.users record is deleted
create or replace trigger on_auth_user_deleted
  after delete on auth.users
  for each row execute function public.handle_user_deletion();

-- Grant necessary permissions for the trigger function
grant delete on table public.users to supabase_auth_admin;