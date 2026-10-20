-- Оплаченные продажи по категориям товаров, от большей к меньшей.
-- Доля категории считается оконной функцией SUM(...) OVER (): она видит
-- итог по всем строкам результата, не схлопывая их.
SELECT
    p.category,
    SUM(ROUND(oi.quantity * oi.unit_price * (1 - oi.discount), 2)) AS paid_sales,
    ROUND(
        100 * SUM(ROUND(oi.quantity * oi.unit_price * (1 - oi.discount), 2))
        / SUM(SUM(ROUND(oi.quantity * oi.unit_price * (1 - oi.discount), 2))) OVER (),
        1
    ) AS share_percent
FROM orders AS o
JOIN order_items AS oi ON oi.order_id = o.id
JOIN products AS p ON p.id = oi.product_id
WHERE o.status = 'paid'
GROUP BY p.category
ORDER BY paid_sales DESC;
