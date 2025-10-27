FROM php:7.4-fpm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpng-dev \
    libjpeg-dev \
    libfreetype6-dev \
    libzip-dev \
    zip \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install PHP extensions
RUN docker-php-ext-configure gd --with-freetype --with-jpeg \
    && docker-php-ext-install -j$(nproc) \
    mysqli \
    pdo_mysql \
    gd \
    zip

# Install Composer
RUN curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Create a compatibility layer for old mysql functions
RUN echo '<?php\n\
// Global mysqli connection for compatibility functions\n\
global $mysqli_connection;\n\
\n\
if (!function_exists("mysql_connect")) {\n\
    function mysql_connect($hostname, $username, $password) {\n\
        global $mysqli_connection;\n\
        $mysqli_connection = new mysqli($hostname, $username, $password);\n\
        if ($mysqli_connection->connect_error) {\n\
            return false;\n\
        }\n\
        return $mysqli_connection;\n\
    }\n\
}\n\
\n\
if (!function_exists("mysql_select_db")) {\n\
    function mysql_select_db($database, $connection = null) {\n\
        global $mysqli_connection;\n\
        $conn = $connection ?: $mysqli_connection;\n\
        return $conn->select_db($database);\n\
    }\n\
}\n\
\n\
if (!function_exists("mysql_query")) {\n\
    function mysql_query($query, $connection = null) {\n\
        global $mysqli_connection;\n\
        $conn = $connection ?: $mysqli_connection;\n\
        return $conn->query($query);\n\
    }\n\
}\n\
\n\
if (!function_exists("mysql_fetch_row")) {\n\
    function mysql_fetch_row($result) {\n\
        if ($result instanceof mysqli_result) {\n\
            return $result->fetch_row();\n\
        }\n\
        return false;\n\
    }\n\
}\n\
\n\
if (!function_exists("mysql_fetch_array")) {\n\
    function mysql_fetch_array($result, $result_type = MYSQLI_BOTH) {\n\
        if ($result instanceof mysqli_result) {\n\
            return $result->fetch_array($result_type);\n\
        }\n\
        return false;\n\
    }\n\
}\n\
\n\
if (!function_exists("mysql_fetch_assoc")) {\n\
    function mysql_fetch_assoc($result) {\n\
        if ($result instanceof mysqli_result) {\n\
            return $result->fetch_assoc();\n\
        }\n\
        return false;\n\
    }\n\
}\n\
\n\
if (!function_exists("mysql_num_rows")) {\n\
    function mysql_num_rows($result) {\n\
        if ($result instanceof mysqli_result) {\n\
            return $result->num_rows;\n\
        }\n\
        return false;\n\
    }\n\
}\n\
\n\
if (!function_exists("mysql_affected_rows")) {\n\
    function mysql_affected_rows($connection = null) {\n\
        global $mysqli_connection;\n\
        $conn = $connection ?: $mysqli_connection;\n\
        return $conn->affected_rows;\n\
    }\n\
}\n\
\n\
if (!function_exists("mysql_insert_id")) {\n\
    function mysql_insert_id($connection = null) {\n\
        global $mysqli_connection;\n\
        $conn = $connection ?: $mysqli_connection;\n\
        return $conn->insert_id;\n\
    }\n\
}\n\
\n\
if (!function_exists("mysql_error")) {\n\
    function mysql_error($connection = null) {\n\
        global $mysqli_connection;\n\
        $conn = $connection ?: $mysqli_connection;\n\
        return $conn->error;\n\
    }\n\
}\n\
\n\
if (!function_exists("mysql_errno")) {\n\
    function mysql_errno($connection = null) {\n\
        global $mysqli_connection;\n\
        $conn = $connection ?: $mysqli_connection;\n\
        return $conn->errno;\n\
    }\n\
}\n\
\n\
if (!function_exists("mysql_close")) {\n\
    function mysql_close($connection = null) {\n\
        global $mysqli_connection;\n\
        $conn = $connection ?: $mysqli_connection;\n\
        return $conn->close();\n\
    }\n\
}\n\
\n\
if (!function_exists("mysql_real_escape_string")) {\n\
    function mysql_real_escape_string($string, $connection = null) {\n\
        global $mysqli_connection;\n\
        $conn = $connection ?: $mysqli_connection;\n\
        if (!$conn) {\n\
            return addslashes($string);\n\
        }\n\
        return $conn->real_escape_string($string);\n\
    }\n\
}\n\
\n\
if (!function_exists("mysql_free_result")) {\n\
    function mysql_free_result($result) {\n\
        if ($result instanceof mysqli_result) {\n\
            return $result->free();\n\
        }\n\
        return false;\n\
    }\n\
}\n\
\n\
// Define MySQL constants if not defined\n\
if (!defined("MYSQL_ASSOC")) define("MYSQL_ASSOC", MYSQLI_ASSOC);\n\
if (!defined("MYSQL_NUM")) define("MYSQL_NUM", MYSQLI_NUM);\n\
if (!defined("MYSQL_BOTH")) define("MYSQL_BOTH", MYSQLI_BOTH);\n\
\n\
?>' > /usr/local/lib/php/mysql_compat.php

# Auto-prepend the compatibility layer
RUN echo "auto_prepend_file = /usr/local/lib/php/mysql_compat.php" >> /usr/local/etc/php/conf.d/mysql_compat.ini

WORKDIR /var/www/public

EXPOSE 9000