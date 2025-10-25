-- Create 'meals' table for food items and meals
create table public.meals (
  id uuid default gen_random_uuid() primary key,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now(),
  
  -- Basic meal information
  name text not null,
  description text,
  meal_type public.meal_type,
  
  -- Brand relationship
  brand_id uuid references public.brands(id) on delete set null,
  
  -- Nutrition information (per serving)
  calories_per_serving numeric(8,2) not null check (calories_per_serving >= 0),
  protein_g numeric(6,2) default 0 check (protein_g >= 0),
  carbs_g numeric(6,2) default 0 check (carbs_g >= 0),
  fat_g numeric(6,2) default 0 check (fat_g >= 0),
  fiber_g numeric(6,2) default 0 check (fiber_g >= 0),
  sugar_g numeric(6,2) default 0 check (sugar_g >= 0),
  sodium_mg numeric(8,2) default 0 check (sodium_mg >= 0),
  
  -- Serving information
  serving_size numeric(8,2) not null check (serving_size > 0),
  serving_unit public.serving_unit_type not null default 'g',
  
  -- Food categorization
  food_category public.food_category_type,
  cuisine_type text,
  dietary_tags text[], -- Array for tags like 'vegan', 'gluten-free', 'keto', etc.
  
  -- Image and verification
  image_url text,
  barcode text unique,
  verified boolean default false,
  created_by uuid references public.users(id) on delete set null,
  
  -- Metadata
  is_active boolean default true,
  popularity_score integer default 0 check (popularity_score >= 0)
);

-- Set up Row Level Security (RLS)
alter table public.meals enable row level security;

-- Policies for meals table
create policy "Meals are viewable by everyone" on public.meals
  for select using (is_active = true);

create policy "Authenticated users can insert meals" on public.meals
  for insert to authenticated with check (true);

create policy "Users can update meals they created" on public.meals
  for update to authenticated using (created_by = auth.uid() or auth.role() = 'admin');

create policy "Users can delete meals they created" on public.meals
  for delete to authenticated using (created_by = auth.uid() or auth.role() = 'admin');

-- Create indexes for better performance
create index idx_meals_name on public.meals using gin(to_tsvector('english', name));
create index idx_meals_calories on public.meals(calories_per_serving);
create index idx_meals_brand_id on public.meals(brand_id);
create index idx_meals_meal_type on public.meals(meal_type);
create index idx_meals_food_category on public.meals(food_category);
create index idx_meals_barcode on public.meals(barcode);
create index idx_meals_created_by on public.meals(created_by);
create index idx_meals_dietary_tags on public.meals using gin(dietary_tags);
create index idx_meals_is_active on public.meals(is_active);

-- Create trigger to update 'updated_at' timestamp
create trigger trigger_meals_updated_at
  before update on public.meals
  for each row execute function public.handle_updated_at();

-- Function to update brand's total_products count
create or replace function public.update_brand_product_count()
returns trigger as $$
begin
  if TG_OP = 'INSERT' then
    update public.brands 
    set total_products = total_products + 1 
    where id = NEW.brand_id;
    return NEW;
  elsif TG_OP = 'DELETE' then
    update public.brands 
    set total_products = total_products - 1 
    where id = OLD.brand_id and total_products > 0;
    return OLD;
  elsif TG_OP = 'UPDATE' then
    if OLD.brand_id != NEW.brand_id then
      -- Decrease old brand count
      update public.brands 
      set total_products = total_products - 1 
      where id = OLD.brand_id and total_products > 0;
      -- Increase new brand count
      update public.brands 
      set total_products = total_products + 1 
      where id = NEW.brand_id;
    end if;
    return NEW;
  end if;
  return null;
end;
$$ language plpgsql;

-- Create triggers to maintain brand product counts
create trigger trigger_meals_brand_count
  after insert or update or delete on public.meals
  for each row execute function public.update_brand_product_count();

-- Grant permissions for Supabase service role (for admin operations)
grant all on table public.meals to service_role;

-- Grant permissions for authenticated users  
grant select, insert, update on table public.meals to authenticated; 