-- samples/sample_data.sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    price DECIMAL(10,2),
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER DEFAULT 1,
    amount DECIMAL(10,2),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

-- КОРРЕКТНЫЕ данные
INSERT INTO users (email, name, created_at, updated_at) VALUES
('alice@example.com', 'Alice Johnson', '2024-01-15 10:00:00', '2024-01-20 14:30:00'),
('bob@example.com', 'Bob Smith', '2024-02-01 09:15:00', '2024-02-10 16:45:00'),
('charlie@example.com', 'Charlie Brown', '2024-03-10 11:20:00', '2024-03-15 08:30:00');

INSERT INTO products (name, price, category) VALUES
('Laptop Gaming', 1299.99, 'electronics'),
('Wireless Mouse', 35.50, 'electronics'),
('Office Chair', 199.99, 'furniture');

INSERT INTO orders (user_id, product_id, quantity, amount, status) VALUES
(1, 1, 1, 1299.99, 'completed'),
(1, 2, 2, 71.00, 'completed'),
(2, 3, 1, 199.99, 'shipped');
