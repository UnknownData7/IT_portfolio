-- Создаем таблицу для 2+ ГБ данных
CREATE TABLE large_dataset (
    id BIGSERIAL PRIMARY KEY,
    large_data TEXT,
    json_data JSONB,
    binary_data BYTEA,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Вставляем 1.5 млн строк, каждая ~1.5 КБ = ~2.25 ГБ
INSERT INTO large_dataset (large_data, json_data, binary_data)
SELECT 
    -- large_data: ~1KB
    repeat(md5(seq::text) || md5(random()::text), 32),
    -- json_data: ~0.5KB
    json_build_object(
        'id', seq,
        'data1', md5(random()::text),
        'data2', md5(random()::text),
        'data3', md5(random()::text),
        'data4', md5(random()::text),
        'data5', md5(random()::text),
        'array_data', array(select md5(random()::text) from generate_series(1, 10)),
        'metadata', json_build_object(
            'created', NOW(),
            'updated', NOW(),
            'version', (random()*10)::int
        )
    ),
    -- binary_data: ~0.1KB
    decode(md5(seq::text) || md5(random()::text), 'hex')
FROM generate_series(1, 1500000) seq;

-- Проверяем размер
SELECT 
    'TOTAL ROWS: ' || COUNT(*)::text as row_count,
    'TABLE SIZE: ' || pg_size_pretty(pg_total_relation_size('large_dataset')) as table_size,
    'DB SIZE: ' || pg_size_pretty(pg_database_size('source_db')) as db_size
FROM large_dataset;
