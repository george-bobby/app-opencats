-- Create 'images' table for meal photos and AI analysis
create table public.images (
  id uuid default gen_random_uuid() primary key,
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now(),
  
  -- Image storage information
  url text not null,
  filename text,
  file_size_bytes bigint check (file_size_bytes > 0),
  mime_type public.mime_type,
  
  -- Image dimensions
  width integer check (width > 0),
  height integer check (height > 0),
  
  -- Relationships
  meal_id uuid references public.meals(id) on delete set null,
  uploaded_by uuid references public.users(id) on delete set null not null,
  
  -- AI Analysis results
  ai_detected_foods text[], -- Array of detected food items
  ai_confidence_score numeric(3,2) check (ai_confidence_score >= 0 and ai_confidence_score <= 1.0),
  ai_estimated_calories numeric(8,2) check (ai_estimated_calories >= 0),
  ai_processing_status public.ai_processing_status_type default 'pending',
  ai_processed_at timestamp with time zone,
  
  -- Image categorization
  image_type public.image_type default 'meal_photo',
  tags text[], -- User or AI generated tags
  
  -- Quality and metadata
  is_public boolean default false,
  is_verified boolean default false,
  blur_hash text, -- For progressive image loading
  exif_data jsonb, -- Store camera/device metadata
  
  -- Moderation
  is_flagged boolean default false,
  moderation_status public.moderation_status_type default 'approved',
  
  -- Storage metadata
  storage_bucket text default 'meal-images',
  storage_path text,
  cdn_url text
);

-- Set up Row Level Security (RLS)
alter table public.images enable row level security;

-- Policies for images table
create policy "Users can view public images" on public.images
  for select using (is_public = true or uploaded_by = auth.uid());

create policy "Users can view their own images" on public.images
  for select using (uploaded_by = auth.uid());

create policy "Users can insert their own images" on public.images
  for insert with check (uploaded_by = auth.uid());

create policy "Users can update their own images" on public.images
  for update using (uploaded_by = auth.uid());

create policy "Users can delete their own images" on public.images
  for delete using (uploaded_by = auth.uid());

-- Create indexes for better performance
create index idx_images_uploaded_by on public.images(uploaded_by);
create index idx_images_meal_id on public.images(meal_id);
create index idx_images_created_at on public.images(created_at desc);
create index idx_images_image_type on public.images(image_type);
create index idx_images_is_public on public.images(is_public);
create index idx_images_ai_processing_status on public.images(ai_processing_status);
create index idx_images_tags on public.images using gin(tags);
create index idx_images_ai_detected_foods on public.images using gin(ai_detected_foods);

-- Create trigger to update 'updated_at' timestamp
create trigger trigger_images_updated_at
  before update on public.images
  for each row execute function public.handle_updated_at();

-- Function to update AI processing timestamp
create or replace function public.update_ai_processed_timestamp()
returns trigger as $$
begin
  if NEW.ai_processing_status = 'completed' and OLD.ai_processing_status != 'completed' then
    NEW.ai_processed_at = now();
  end if;
  return NEW;
end;
$$ language plpgsql;

-- Create trigger to auto-update AI processed timestamp
create trigger trigger_images_ai_processed
  before update on public.images
  for each row execute function public.update_ai_processed_timestamp();

-- Create a view for image analytics
create or replace view public.image_analytics as
select 
  uploaded_by,
  count(*) as total_images,
  count(case when ai_processing_status = 'completed' then 1 end) as processed_images,
  avg(ai_confidence_score) as avg_confidence_score,
  count(case when is_public = true then 1 end) as public_images,
  count(case when image_type = 'meal_photo' then 1 end) as meal_photos,
  count(case when image_type = 'nutrition_label' then 1 end) as nutrition_labels,
  max(created_at) as last_upload_date,
  sum(file_size_bytes) as total_storage_bytes
from public.images
group by uploaded_by;

-- Grant permissions for Supabase service role (for admin operations)
grant all on table public.images to service_role;

-- Grant permissions for authenticated users  
grant select, insert, update, delete on table public.images to authenticated; 