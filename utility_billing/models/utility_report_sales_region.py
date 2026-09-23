from odoo import fields, models, tools


class UtilityReportSalesRegion(models.Model):
    _name = 'utility.report.sales.region'
    _description = 'تقرير مبيعات وسداد المناطق'
    _auto = False
    _order = 'period_id desc, region_id, sub_region_id, customer_category'

    period_id = fields.Many2one('date.range', string='الفترة', readonly=True)
    region_id = fields.Many2one('utility.region', string='المنطقة', readonly=True)
    sub_region_id = fields.Many2one(
        'utility.region', string='المنطقة الفرعية', readonly=True
    )
    customer_category = fields.Char(string='فئة المشترك', readonly=True)

    sale_count = fields.Integer(
        string='عدد المبيع', readonly=True, group_operator='sum'
    )
    consumption_kwh = fields.Float(
        string='المبيع ك.و', readonly=True, group_operator='sum'
    )
    sale_amount = fields.Float(
        string='المبيع بالريال', readonly=True, group_operator='sum'
    )
    service_fees = fields.Float(
        string='رسوم الخدمات', readonly=True, group_operator='sum'
    )
    council_fees = fields.Float(
        string='رسوم المجلس المحلي', readonly=True, group_operator='sum'
    )
    energy_fees = fields.Float(
        string='رسوم الطاقة', readonly=True, group_operator='sum'
    )
    teacher_fund = fields.Float(
        string='صندوق المعلم', readonly=True, group_operator='sum'
    )
    other_adjustments = fields.Float(
        string='تسويات', readonly=True, group_operator='sum'
    )
    adjustments = fields.Float(
        string='تسويات مبيع', readonly=True, group_operator='sum'
    )
    gross_sales = fields.Float(
        string='إجمالي المبيع', readonly=True, group_operator='sum'
    )
    payments = fields.Float(
        string='السداد', readonly=True, group_operator='sum'
    )
    remaining = fields.Float(
        string='المتبقي من المبيع', readonly=True, group_operator='sum'
    )

    def init(self):
        cr = self.env.cr
        cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_sale_order_date_range_paid
                ON sale_order (date_range_id)
                WHERE state IN ('sale', 'done') AND date_range_id IS NOT NULL
        """)
        cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_utility_customer_region_area
                ON utility_customer (region_id, area_id)
        """)

        tools.drop_view_if_exists(cr, self._table)
        cr.execute("""
            CREATE OR REPLACE VIEW utility_report_sales_region AS (
                WITH line_amounts AS (
                    SELECT
                        sol.order_id,
                        SUM(CASE WHEN sol.meter_line_type IN ('service_charge', 'fixed_fee')
                            THEN sol.price_subtotal ELSE 0 END) AS service_fees,
                        SUM(CASE WHEN sol.meter_line_type = 'municipality'
                            THEN sol.price_subtotal ELSE 0 END) AS council_fees,
                        SUM(CASE WHEN sol.meter_line_type = 'consumption'
                            THEN sol.price_subtotal ELSE 0 END) AS energy_fees,
                        SUM(CASE WHEN sol.meter_line_type = 'consumption'
                            THEN sol.product_uom_qty ELSE 0 END) AS consumption_kwh,
                        SUM(CASE WHEN sol.meter_line_type = 'mu_allim'
                            THEN sol.price_subtotal ELSE 0 END) AS teacher_fund,
                        SUM(CASE WHEN sol.meter_line_type = 'discount'
                            THEN sol.price_subtotal ELSE 0 END) AS adjustments
                    FROM sale_order_line sol
                    GROUP BY sol.order_id
                ),
                sales AS (
                    SELECT
                        so.date_range_id AS period_id,
                        customer.region_id AS region_id,
                        customer.area_id AS sub_region_id,
                        COALESCE(category.name->>'ar_001', category.name->>'en_US', 'غير محدد') AS customer_category,
                        COUNT(so.id)::integer AS sale_count,
                        SUM(COALESCE(lines.consumption_kwh, 0)) AS consumption_kwh,
                        SUM(COALESCE(so.amount_energy, 0)) AS sale_amount,
                        SUM(COALESCE(lines.service_fees, 0)) AS service_fees,
                        SUM(COALESCE(lines.council_fees, 0)) AS council_fees,
                        SUM(COALESCE(lines.energy_fees, 0)) AS energy_fees,
                        SUM(COALESCE(lines.teacher_fund, 0)) AS teacher_fund,
                        SUM(COALESCE(lines.adjustments, 0)) AS adjustments,
                        0::numeric AS other_adjustments,
                        SUM(COALESCE(so.amount_total, 0)) AS gross_sales,
                        SUM(COALESCE(so.amount_paid, 0)) AS payments,
                        SUM(COALESCE(so.balance_due, 0)) AS remaining
                    FROM sale_order so
                    JOIN utility_customer customer ON customer.id = so.customer_id
                    LEFT JOIN utility_subscriber_category category
                        ON category.id = customer.category_id
                    LEFT JOIN line_amounts lines ON lines.order_id = so.id
                    WHERE so.state IN ('sale', 'done')
                      AND so.date_range_id IS NOT NULL
                    GROUP BY so.date_range_id, customer.region_id, customer.area_id, category.name
                ),
                billing_adjustments AS (
                    SELECT
                        adjustment.billing_period_id AS period_id,
                        customer.region_id AS region_id,
                        customer.area_id AS sub_region_id,
                        COALESCE(category.name->>'ar_001', category.name->>'en_US', 'غير محدد') AS customer_category,
                        0::integer AS sale_count,
                        0::numeric AS consumption_kwh,
                        0::numeric AS sale_amount,
                        0::numeric AS service_fees,
                        0::numeric AS council_fees,
                        0::numeric AS energy_fees,
                        0::numeric AS teacher_fund,
                        0::numeric AS adjustments,
                        SUM(COALESCE(adjustment.difference_amount, 0)) AS other_adjustments,
                        0::numeric AS gross_sales,
                        0::numeric AS payments,
                        0::numeric AS remaining
                    FROM utility_billing_adjustment adjustment
                    JOIN utility_customer customer ON customer.id = adjustment.customer_id
                    LEFT JOIN utility_subscriber_category category
                        ON category.id = customer.category_id
                    WHERE adjustment.state IN ('approved', 'applied')
                      AND adjustment.billing_period_id IS NOT NULL
                    GROUP BY adjustment.billing_period_id, customer.region_id,
                        customer.area_id, category.name
                ),
                report_rows AS (
                    SELECT * FROM sales
                    UNION ALL
                    SELECT * FROM billing_adjustments
                ),
                aggregated AS (
                    SELECT
                        period_id, region_id, sub_region_id, customer_category,
                        SUM(sale_count)::integer AS sale_count,
                        SUM(consumption_kwh) AS consumption_kwh,
                        SUM(sale_amount) AS sale_amount,
                        SUM(service_fees) AS service_fees,
                        SUM(council_fees) AS council_fees,
                        SUM(energy_fees) AS energy_fees,
                        SUM(teacher_fund) AS teacher_fund,
                        SUM(adjustments) AS adjustments,
                        SUM(other_adjustments) AS other_adjustments,
                        SUM(gross_sales) AS gross_sales,
                        SUM(payments) AS payments,
                        SUM(remaining) AS remaining
                    FROM report_rows
                    GROUP BY period_id, region_id, sub_region_id, customer_category
                )
                SELECT
                    row_number() OVER (
                        ORDER BY period_id DESC, region_id, sub_region_id, customer_category
                    )::integer AS id,
                    period_id,
                    region_id,
                    sub_region_id,
                    customer_category,
                    sale_count,
                    consumption_kwh,
                    sale_amount,
                    service_fees,
                    council_fees,
                    energy_fees,
                    teacher_fund,
                    adjustments,
                    other_adjustments,
                    gross_sales,
                    payments,
                    remaining
                FROM aggregated
            )
        """)

