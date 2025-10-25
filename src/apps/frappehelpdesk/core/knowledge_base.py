import asyncio
import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from faker import Faker
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from apps.frappehelpdesk.config.settings import settings
from apps.frappehelpdesk.core.users import USERS_CACHE_FILE
from apps.frappehelpdesk.utils.frappe_client import FrappeClient
from common.logger import logger


fake = Faker()
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Cache file paths
CATEGORIES_CACHE_FILE = Path(Path(__file__).parent.parent, "data", "generated", "knowledge_base_categories.json")
ARTICLES_CACHE_FILE = Path(Path(__file__).parent.parent, "data", "generated", "knowledge_base_articles.json")


class Categories(BaseModel):
    categories: list[str] = Field(description="The list of knowledge base categories")


class Article(BaseModel):
    title: str = Field(description="The title of the article")
    content: str = Field(description="The content of the article")


async def generate_kb_categories(number_of_categories: int):
    """
    Generate knowledge base categories using GPT and save to JSON file.
    Always generates fresh data and overwrites existing cache.
    """
    logger.start(f"Generating {number_of_categories} knowledge base categories...")

    logger.info("Generating article categories...")
    categories = await openai_client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": f"""You are a helpful assistant that generates {number_of_categories} categories of knowledge base for a Helpdesk system. 
                    We are {settings.COMPANY_NAME} and we are a {settings.DATA_THEME_SUBJECT}.
                    Some additional information that can be helpful:
                    - Today is {datetime.now().strftime("%Y-%m-%d")}
                    """,
            }
        ],
        response_format=Categories,
    )

    categories_data = categories.choices[0].message.parsed.categories

    # Save to cache
    try:
        # Ensure the data directory exists
        CATEGORIES_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        cache_data = {"categories": categories_data}

        with CATEGORIES_CACHE_FILE.open("w") as f:
            json.dump(cache_data, f, indent=2)
        logger.info(f"Cached {len(categories_data)} categories to {CATEGORIES_CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Error saving categories cache: {e}")

    logger.succeed(f"Generated {len(categories_data)} knowledge base categories")


async def seed_kb_categories():
    """
    Read knowledge base categories from cache file and insert them into Frappe.
    """
    logger.start("Seeding knowledge base categories...")

    # Load categories from cache
    if not CATEGORIES_CACHE_FILE.exists():
        logger.fail("Categories cache file not found. Please run generate_kb_categories first.")
        return

    try:
        with CATEGORIES_CACHE_FILE.open() as f:
            cache_data = json.load(f)
            categories_data = cache_data.get("categories", [])
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.fail(f"Error loading categories cache: {e}")
        return

    if not categories_data:
        logger.fail("No categories found in cache file")
        return

    successful_categories = 0

    async with FrappeClient() as client:
        for category in categories_data:
            try:
                await client.insert(
                    {
                        "doctype": "HD Article Category",
                        "category_name": category,
                    }
                )
                logger.info(f"Inserted knowledge base category: {category}")
                successful_categories += 1
            except Exception as e:
                logger.warning(f"Error inserting knowledge base category: {e}")
                import traceback

                logger.warning(traceback.format_exc())

    logger.succeed(f"Seeded {successful_categories}/{len(categories_data)} knowledge base categories")


async def insert_categories(number_of_categories: int):
    """
    Legacy function for backward compatibility.
    Try to load from cache first, generate if needed, then seed to Frappe.
    """
    # Try to load from cache first
    categories_data = None
    if CATEGORIES_CACHE_FILE.exists():
        try:
            with CATEGORIES_CACHE_FILE.open() as f:
                cache_data = json.load(f)
                # Check if we have the right number of categories cached
                if len(cache_data.get("categories", [])) >= number_of_categories:
                    logger.info(f"Loading {number_of_categories} categories from cache")
                    # Use only the requested number of categories
                    categories_data = cache_data["categories"][:number_of_categories]
        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.warning(f"Error loading categories cache, will generate new categories: {e}")
            categories_data = None

    # Generate new categories if not cached or cache is insufficient
    if categories_data is None:
        await generate_kb_categories(number_of_categories)

    # Seed the categories (seed_kb_categories reads from cache, not parameter)
    await seed_kb_categories()


async def generate_kb_articles(number_of_articles: int):
    """
    Generate knowledge base articles using GPT and save to JSON file.
    Always generates fresh data and overwrites existing cache.
    Uses data from JSON files instead of querying Frappe client.
    """
    logger.start(f"Generating {number_of_articles} knowledge base articles...")

    # Load categories from JSON cache instead of querying database
    if not CATEGORIES_CACHE_FILE.exists():
        logger.fail("Categories cache file not found. Please run generate_kb_categories first.")
        return

    try:
        with CATEGORIES_CACHE_FILE.open() as f:
            categories_cache = json.load(f)
            categories_data = categories_cache.get("categories", [])
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.fail(f"Error loading categories cache: {e}")
        return

    if not categories_data:
        logger.fail("No categories found in cache file")
        return

    # Load users from JSON cache for author assignment
    if not USERS_CACHE_FILE.exists():
        logger.fail("Users cache file not found. Please run generate_users first.")
        return

    try:
        with USERS_CACHE_FILE.open() as f:
            users_cache = json.load(f)
            users_data = users_cache.get("users", [])
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.fail(f"Error loading users cache: {e}")
        return

    if not users_data:
        logger.fail("No users found in cache file")
        return

    # Filter users to only include company domain users
    domain = settings.COMPANY_NAME.lower()
    domain = "".join(c for c in domain if c.isalnum()) + ".com"
    company_users = [user for user in users_data if user.get("email", "").endswith(f"@{domain}")]

    if not company_users:
        logger.fail(f"No company users found for domain {domain}")
        return

    logger.info(f"Generating {number_of_articles} articles using {len(categories_data)} cached categories and {len(company_users)} company users")
    generated_articles = []

    concurrency_limit = 16
    semaphore = asyncio.Semaphore(concurrency_limit)

    async def create_article(category_name, article_index):
        async with semaphore:
            try:
                logger.info(f"Generating article {article_index + 1}/{number_of_articles} for category: {category_name}")

                # Generate existing article titles from cache to avoid duplicates
                existing_titles = []
                if ARTICLES_CACHE_FILE.exists():
                    try:
                        with ARTICLES_CACHE_FILE.open() as f:
                            existing_cache = json.load(f)
                            existing_titles = [article.get("title", "") for article in existing_cache.get("articles", [])]
                    except Exception:
                        pass  # Ignore cache read errors

                articles = await openai_client.beta.chat.completions.parse(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": f"""You are a helpful assistant that creates a knowledge base article for a Helpdesk system. 
                            Create a knowledge base article for the category: {category_name}.
                            Use HTML for formatting.
                            Avoid creating duplicated articles. Here is the list of existing article titles to avoid:
                            {existing_titles}
                            Article titles should be unique and specific.
                            New article titles should be drastically different from the existing articles.
                            We are {settings.COMPANY_NAME} and we are a {settings.DATA_THEME_SUBJECT}.
                            Some additional information that can be helpful:
                            - Today is {datetime.now().strftime("%Y-%m-%d")}
                            """,
                        }
                    ],
                    response_format=Article,
                )
                article = articles.choices[0].message.parsed

                # Select a random user as the author
                author_user = fake.random_element(company_users)

                # Store article data for caching
                article_data = {
                    "title": article.title,
                    "content": article.content,
                    "category_name": category_name,
                    "author": {
                        "email": author_user["email"],
                        "first_name": author_user["first_name"],
                        "last_name": author_user["last_name"],
                    },
                }

                return article_data
            except Exception as e:
                logger.warning(f"Error generating article: {e}")
                return None

    # Create tasks for all articles
    tasks = []
    for i in range(number_of_articles):
        category_name = fake.random_element(categories_data)
        tasks.append(create_article(category_name, i))

    # Generate all articles
    results = await asyncio.gather(*tasks)
    generated_articles = [result for result in results if result is not None]

    # Save to cache
    try:
        # Ensure the data directory exists
        ARTICLES_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        cache_data = {"articles": generated_articles}

        with ARTICLES_CACHE_FILE.open("w") as f:
            json.dump(cache_data, f, indent=2)
        logger.info(f"Cached {len(generated_articles)} articles to {ARTICLES_CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Error saving articles cache: {e}")

    logger.succeed(f"Generated {len(generated_articles)} knowledge base articles")


async def seed_kb_articles():
    """
    Read knowledge base articles from cache file and insert them into Frappe.
    """
    logger.start("Seeding knowledge base articles...")

    # Load articles from cache
    if not ARTICLES_CACHE_FILE.exists():
        logger.fail("Articles cache file not found. Please run generate_kb_articles first.")
        return

    try:
        with ARTICLES_CACHE_FILE.open() as f:
            cache_data = json.load(f)
            articles_data = cache_data.get("articles", [])
    except (json.JSONDecodeError, KeyError, Exception) as e:
        logger.fail(f"Error loading articles cache: {e}")
        return

    if not articles_data:
        logger.fail("No articles found in cache file")
        return

    # Get fresh categories list to ensure they exist
    async with FrappeClient() as client:
        current_categories = await client.get_list(
            "HD Article Category",
            fields=["name", "category_name"],
            limit_page_length=settings.LIST_LIMIT,
        )

    if not current_categories:
        logger.fail("No categories found in database. Please seed categories first.")
        return

    successful_articles = 0

    # Create articles from cached data
    for article_data in articles_data:
        try:
            # Use the author information stored in the cache
            author_info = article_data.get("author")
            if author_info and author_info.get("email"):
                author_email = author_info["email"]
            else:
                # Fallback: query for any company user if no author info
                domain = settings.COMPANY_NAME.lower()
                domain = "".join(c for c in domain if c.isalnum()) + ".com"

                async with FrappeClient() as client:
                    users = await client.get_list(
                        "User",
                        fields=["name", "email"],
                        filters=[["email", "LIKE", f"%{domain}"]],
                        limit_page_length=settings.LIST_LIMIT,
                    )

                if not users:
                    logger.warning("No company users found, skipping article")
                    continue

                author_email = fake.random_element(users)["email"]
                logger.warning(f"No author info in cache for article '{article_data['title']}', using random user: {author_email}")

            # Create a new client instance for the author
            async with FrappeClient(username=author_email, password=settings.USER_PASSWORD) as impersonated_user:
                # Find category ID by name
                category_name = article_data.get("category_name")
                category_id = None

                if category_name:
                    # Find the category ID by name
                    matching_categories = [cat for cat in current_categories if cat["category_name"] == category_name]
                    if matching_categories:
                        category_id = matching_categories[0]["name"]
                    else:
                        # If no match found, use a random category
                        category_id = fake.random_element(current_categories)["name"]
                        logger.warning(f"Category '{category_name}' not found, using random category")
                else:
                    # If no category info at all, use random
                    category_id = fake.random_element(current_categories)["name"]
                    logger.warning("No category info in cached article, using random category")

                await impersonated_user.insert(
                    {
                        "title": article_data["title"],
                        "status": fake.random_element(
                            OrderedDict(
                                [
                                    ("Draft", 0.15),
                                    ("Published", 0.85),
                                ]
                            )
                        ),
                        "category": category_id,
                        "title_slug": article_data["title"].lower().replace(" ", "-"),
                        "content": article_data["content"],
                        "doctype": "HD Article",
                    }
                )

                author_name = f"{author_info.get('first_name', '')} {author_info.get('last_name', '')}" if author_info else author_email
                logger.info(f"Inserted article: {article_data['title']} (author: {author_name})")
                successful_articles += 1
        except Exception as e:
            logger.warning(f"Error inserting article: {e}")

    logger.succeed(f"Seeded {successful_articles}/{len(articles_data)} knowledge base articles")
