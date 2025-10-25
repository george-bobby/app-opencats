# Spree Commerce 

## Prerequisites
- Docker and Docker Compose running
- Virtual environment activated: `source .venv/bin/activate`
- Anthropic API key (requied, for data generation)
- Pexels API key (optional, for product images)

## Setup Process

### 1. Start the container
```bash
python cli.py spree up
```
Options:
- `-d, --detach` - Run in detached mode

**Important:** The system will automatically prepare the database during startup. This process may take a few minutes on first run.

### 2. Verify the installation
Before proceeding to seed the database, make sure you can visit `http://localhost:3000` without any error. This confirms that the Docker containers are properly running and Spree is accessible.

### 3. Seed the database
```bash
python cli.py spree seed
```

**Note:** Only run the seed command after confirming that `http://localhost:3000` is accessible without errors.

### 4. Access Spree Commerce
1. Open `http://localhost:3000/` in your browser
2. Login with the configured credentials:
   - Email: `admin@fuzzloft.com`
   - Password: `spree123`

### 5. Generate additional data (optional)
```bash
python cli.py spree generate
```

## Available Commands

### Start Services
```bash
python cli.py spree up [-d]
```
- `up` - Start Spree services
- `-d, --detach` - Run in detached mode

### Stop Services
```bash
python cli.py spree down [-t TIMEOUT]
```
- `down` - Stop services and cleanup
- `-t, --timeout` - Timeout in seconds (default: 10)

### View Logs
```bash
python cli.py spree logs [-f]
```
- `logs` - View container logs
- `-f, --follow` - Follow log output

### Seed Data
```bash
python cli.py spree seed
```
- Creates initial data including:
  - Tax categories and rates
  - Shipping methods
  - Refund reasons
  - Reimbursement types
  - Return authorization reasons
  - User roles
  - Payment methods
  - Users (admin and customers)
  - Taxonomies and taxons
  - Option types
  - Properties and prototypes
  - Promotion categories
  - Stock locations
  - Products
  - Stock items and transfers
  - Orders
  - Promotions
  - Return authorizations
  - Pages and menus
  - Product images

### Generate Test Data
```bash
python cli.py spree generate [OPTIONS]
```
Options:
- `--taxonomies` - Number of taxonomies (default: 3)
- `--tax-categories` - Number of tax categories (default: 8)
- `--tax-rates` - Number of tax rates (default: 10)
- `--shipping-methods` - Number of shipping methods (default: 5)
- `--refund-reasons` - Number of refund reasons (default: 10)
- `--reimbursement-types` - Number of reimbursement types (default: 5)
- `--rma-reasons` - Number of return reasons (default: 10)
- `--payment-methods` - Number of payment methods (default: 5)
- `--dashboard-users` - Number of admin users (default: 10)
- `--customer-users` - Number of customer users (default: 100)
- `--min-taxons-per-taxonomy` - Minimum taxons per taxonomy (default: 5)
- `--max-taxons-per-taxonomy` - Maximum taxons per taxonomy (default: 10)
- `--option-types` - Number of option types (default: 5)
- `--properties` - Number of properties (default: 10)
- `--prototypes` - Number of prototypes (default: 10)
- `--products` - Number of products (default: 50)
- `--stock-locations` - Number of stock locations (default: 5)
- `--pages` - Number of CMS pages (default: 8)
- `--header-menu-items` - Number of header menu items (default: 6)
- `--footer-menu-items` - Number of footer menu items (default: 10)
- `--min-images-per-product` - Minimum images per product (default: 3)
- `--max-images-per-product` - Maximum images per product (default: 5)
- `--promotion-categories` - Number of promotion categories (default: 5)
- `--stock-transfers` - Number of stock transfers (default: 50)
- `--promotions` - Number of promotions (default: 10)
- `--orders` - Number of orders (default: 300)
- `--rmas` - Number of return authorizations (default: 50)
- `--stock-multiplier` - Multiplier for stock items (default: 1)

## Example Usage

### Basic setup
```bash
python cli.py spree up
# Wait for database preparation to complete
# Verify http://localhost:3000 is accessible
python cli.py spree seed
```

### Generate custom data
```bash
python cli.py spree generate --products 100 --orders 500 --customer-users 200
```

### Clean shutdown
```bash
python cli.py spree down
```

## Configuration

The app uses environment variables for configuration. Default settings include:
- **Database**: PostgreSQL on port 5432
- **Redis**: Redis on port 6379
- **Spree URL**: http://localhost:3000
- **Admin Email**: admin@fuzzloft.com
- **Store Name**: Fuzzloft (Pet Supplies eCommerce Store)
- **Anthropic API Key**: Set to "DUMMY" by default, please provide a correct API key

You can customize these settings by modifying the environment variables or the `config/settings.py` file.
