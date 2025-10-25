FROM node:20-alpine

# Install git, PostgreSQL client, and bash
RUN apk add --no-cache git postgresql-client bash curl

# Set working directory
WORKDIR /app

# Clone Medusa starter project
RUN git clone https://github.com/medusajs/medusa-starter-default.git . && \
    rm -rf .git

# Install dependencies
RUN npm install

# Create medusa-config.js with Docker-friendly settings (using .js instead of .ts to avoid compilation issues)
RUN cat > medusa-config.js <<EOF
const { loadEnv, defineConfig } = require("@medusajs/framework/utils")

loadEnv(process.env.NODE_ENV || "development", process.cwd())

module.exports = defineConfig({
  projectConfig: {
    databaseUrl: process.env.DATABASE_URL,
    redisUrl: process.env.REDIS_URL,
    http: {
      storeCors: process.env.STORE_CORS || "http://localhost:8000",
      adminCors: process.env.ADMIN_CORS || "http://localhost:7001,http://localhost:9000",
      authCors: process.env.AUTH_CORS || "http://localhost:9000",
      jwtSecret: process.env.JWT_SECRET || "supersecret",
      cookieSecret: process.env.COOKIE_SECRET || "supersecret",
    },
    databaseDriverOptions: {
      ssl: false,
      sslmode: "disable",
    },
  },
  admin: {
    backendUrl: process.env.MEDUSA_BACKEND_URL || "http://localhost:9000",
  },
})
EOF

# Expose port
EXPOSE 9000

# Create a startup script that includes admin user creation
RUN cat > /usr/local/bin/start.sh <<EOF
#!/bin/sh
echo "🔄 Waiting for PostgreSQL..."
until pg_isready -h postgres -U postgres; do sleep 2; done
echo "✅ PostgreSQL ready!"
echo "🗄️ Running migrations..."
npx medusa db:migrate
echo "🌱 Seeding database..."
npm run seed 2>/dev/null || echo "No seed script found, continuing..."
echo "👤 Creating admin user..."
npx medusa user -e \${ADMIN_EMAIL:-admin@example.com} -p \${ADMIN_PASSWORD:-supersecret} || echo "Admin user already exists or creation failed"
echo "🚀 Starting Medusa server..."
npm run dev
EOF

RUN chmod +x /usr/local/bin/start.sh

# Start command
CMD ["start.sh"]