-- Сумма каждого оплаченного заказа.
-- Сумма позиции = количество * цена * (1 - скидка), округлённая до копейки;
-- сумма заказа = сумма его позиций. JOIN соединяет заказ, клиента и позиции.
SELECT
    o.id AS order_id,
    c.name AS customer,
    o.paid_at,
    COUNT(*) AS items,
    SUM(ROUND(oi.quantity * oi.unit_price * (1 - oi.discount), 2)) AS order_total
FROM orders AS o
JOIN customers AS c ON c.id = o.customer_id
JOIN order_items AS oi ON oi.order_id = o.id
WHERE o.status = 'paid'
GROUP BY o.id, c.name, o.paid_at
ORDER BY o.paid_at;
