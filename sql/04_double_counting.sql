-- Ловушка двойного подсчёта при JOIN «один ко многим».
-- У позиции может быть несколько возвратов. Если присоединить refunds
-- к позициям и потом сложить суммы позиций, позиция с двумя возвратами
-- попадёт в сумму дважды. Правильно - сначала свести каждую таблицу
-- к одной строке на ключ (или посчитать суммы отдельно), потом соединять.
WITH paid_items AS (
    SELECT
        oi.id,
        ROUND(oi.quantity * oi.unit_price * (1 - oi.discount), 2) AS line_total
    FROM orders AS o
    JOIN order_items AS oi ON oi.order_id = o.id
    WHERE o.status = 'paid'
)
SELECT
    (
        SELECT SUM(pi.line_total)
        FROM paid_items AS pi
        LEFT JOIN refunds AS r ON r.order_item_id = pi.id
    ) AS naive_sales,
    (SELECT SUM(line_total) FROM paid_items) AS correct_sales,
    (SELECT SUM(amount) FROM refunds) AS refunds;
