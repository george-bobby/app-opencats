FROM ruby:3.4.3-slim-bullseye

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    default-libmysqlclient-dev \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libssl-dev \
    libyaml-dev \
    libreadline-dev \
    zlib1g-dev \
    libncurses5-dev \
    libgdbm-dev \
    libnss3-dev \
    libsqlite3-dev \
    libpq-dev \
    imagemagick \
    libvips-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20.x
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs

# Set environment variables
ENV BUNDLE_PATH=/bundle_path
ENV APP_DIR=/app
ENV LANG=C.UTF-8
ENV RAILS_ENV=development
ENV RACK_ENV=development

# Set working directory
WORKDIR $APP_DIR
RUN git clone https://github.com/antiwork/gumroad.git --branch production-ef15aea58675/2025-06-06-07-49-28 --single-branch --depth 1 $APP_DIR
RUN rm -f $APP_DIR/Gemfile.lock

# Create app user and directories
RUN useradd -ms /bin/bash app \
    && mkdir -p $APP_DIR \
    && mkdir -p $BUNDLE_PATH \
    && mkdir -p $APP_DIR/log \
    && mkdir -p $APP_DIR/tmp

# Set ownership and permissions - app user needs to write to these files
RUN chown -R app:app $APP_DIR \
    && chown -R app:app $BUNDLE_PATH \
    && chmod -R 755 $BUNDLE_PATH \
    && chmod -R 755 $APP_DIR

# Install Ruby gems
RUN gem install bundler
RUN bundle config set --local without 'production staging'
RUN bundle install --verbose --jobs=4
RUN gem install dotenv

# Install Node.js dependencies
RUN corepack enable
RUN npm install

RUN if [ "$(uname -m)" = "x86_64" ]; then \
    apt-get update && apt-get install -y libnss3-tools \
    && curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64" \
    && chmod +x mkcert-v*-linux-amd64 \
    && cp mkcert-v*-linux-amd64 /usr/local/bin/mkcert \
    && rm mkcert-v*-linux-amd64; \
    else \
    apt-get update && apt-get install -y libnss3-tools \
    && curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/arm64" \
    && chmod +x mkcert-v*-linux-arm64 \
    && cp mkcert-v*-linux-arm64 /usr/local/bin/mkcert \
    && rm mkcert-v*-linux-arm64; \
    fi

# Set proper ownership and permissions
RUN chown -R app:app $APP_DIR \
    && chmod -R 755 $APP_DIR \
    && chmod -R 770 $APP_DIR/tmp \
    && chmod -R 770 $APP_DIR/log

RUN rm $APP_DIR/.env.*
COPY patches/Procfile $APP_DIR/Procfile
COPY patches/domain.rb $APP_DIR/config/domain.rb
COPY patches/development.rb $APP_DIR/config/environments/development.rb
COPY patches/application_controller.rb $APP_DIR/app/controllers/application_controller.rb
COPY patches/orders_controller.rb $APP_DIR/app/controllers/orders_controller.rb
COPY patches/development.js $APP_DIR/config/webpack/development.js
COPY patches/common.js $APP_DIR/config/webpack/common.js
RUN mkdir -p $APP_DIR/storage

RUN gem install foreman
RUN bin/generate_ssl_certificates
