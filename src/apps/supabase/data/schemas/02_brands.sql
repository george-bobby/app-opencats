-- Create 'brands' table for food brands
create table public.brands (
  id uuid default gen_random_uuid() primary key,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now(),
  
  -- Brand information
  name text not null unique,
  description text,
  logo_url text,
  website_url text,
  
  -- Brand metrics
  popularity_rank integer default 0 check (popularity_rank >= 0),
  verified boolean default false,
  total_products integer default 0 check (total_products >= 0),
  
  -- Brand classification
  category public.brand_category_type,
  country_origin text,
  
  -- Metadata
  is_active boolean default true
);

-- Set up Row Level Security (RLS)
alter table public.brands enable row level security;

-- Policies for brands table
create policy "Brands are viewable by everyone" on public.brands
  for select using (is_active = true);

create policy "Only authenticated users can insert brands" on public.brands
  for insert to authenticated with check (true);

create policy "Only authenticated users can update brands" on public.brands
  for update to authenticated using (true);

-- Create indexes for better performance
create index idx_brands_name on public.brands(name);
create index idx_brands_popularity_rank on public.brands(popularity_rank desc);
create index idx_brands_category on public.brands(category);
create index idx_brands_is_active on public.brands(is_active);

-- Create trigger to update 'updated_at' timestamp
create trigger trigger_brands_updated_at
  before update on public.brands
  for each row execute function public.handle_updated_at();

-- Grant permissions for Supabase service role (for admin operations)
grant all on table public.brands to service_role;

-- Grant permissions for authenticated users  
grant select, insert, update on table public.brands to authenticated; 