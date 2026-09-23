from odoo import fields, models, tools


class UtilityReportSalesCollector(models.Model):
    _name = 'utility.report.sales.collector'
    _description = 'تقرير إنجاز التحصيل والمبيع بحسب الكاشف'
    _auto = False
    _order = 'period_id desc, collector_id'

    period_id = fields.Many2one('date.range', string='الفترة', readonly=True)
    collector_id = fields.Many2one(
        'utility.staff', string='الكاشف / المتحصل', readonly=True
    )
    company_id = fields.Many2one('res.company', string='الشركة', readonly=True)
    region_id = fields.Many2one('utility.region', string='المنطقة', readonly=True)
    area_id = fields.Many2one(
        'utility.region', string='المنطقة الفرعية', readonly=True
    )

    invoice_count = fields.Integer(
        string='عدد الفواتير الصادره', readonly=True, group_operator='sum'
    )
    consumption_kwh = fields.Float(
        string='المبيع ك.و', readonly=True, group_operator='sum'
    )
    sale_amount = fields.Float(
        string='المبيع ريال', readonly=True, group_operator='sum'
    )
    gross_sales = fields.Float(
        string='اجمالي المبيع', readonly=True, group_operator='sum'
    )
    cumulative_collection = fields.Float(
        string='التحصيل التراكمي', readonly=True, group_operator='sum'
    )
    today_collection = fields.Float(
        string='تحصيل اليوم', readonly=True, group_operator='sum'
    )
    total_collection = fields.Float(
        string='اجمالي التحصيل', readonly=True, group_operator='sum'
    )
    collection_rate = fields.Float(
        string='نسبة التحصيل', readonly=True, group_operator='avg'
    )
    cumulative_paid_invoices = fields.Integer(
        string='الفواتير المسدده تراكمي', readonly=True,
        group_operator='sum'
    )
    today_paid_invoices = fields.Integer(
        string='الفواتير المسدده اليوم', readonly=True,
        group_operator='sum'
    )
    total_paid_invoices = fields.Integer(
        string='اجمالي الفواتير المسدده', readonly=True,
        group_operator='sum'
    )
    paid_invoice_rate = fields.Float(
        string='نسبه الفواتير المسدده', readonly=True,
        group_operator='avg'
    )
    remaining_sales = fields.Float(
        string='المتبقي من المبيع', readonly=True, group_operator='sum'
    )
    remaining_invoices = fields.Integer(
        string='الفواتير المتبقيه', readonly=True, group_operator='sum'
    )

    def init(self):
        cr = self.env.cr
        cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_res_users_route_rel_route_user
                ON res_users_route_rel (route_id, user_id)
        """)
        cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_utility_staff_user_company
                ON utility_staff (user_id, company_id)
                WHERE active IS TRUE
        """)
        cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_payment_allocation_sale_state
                ON utility_payment_allocation (sale_order_id, state)
                WHERE state = 'reconciled'
        """)

        tools.drop_view_if_exists(cr, self._table)
        cr.execute("""
            CREATE OR REPLACE VIEW utility_report_sales_collector AS (
                WITH collector_group AS (
                    SELECT data.res_id AS group_id
                    FROM ir_model_data data
                    WHERE data.module = 'utility_core'
                      AND data.name = 'group_utility_collector'
                      AND data.model = 'res.groups'
                ),
                collector_assignments AS (
                    SELECT
                        route_user.route_id,
                        staff.id AS collector_id,
                        staff.company_id
                    FROM res_users_route_rel route_user
                    JOIN utility_staff staff
                      ON staff.user_id = route_user.user_id
                     AND staff.active IS TRUE
                    JOIN res_groups_users_rel group_user
                      ON group_user.uid = route_user.user_id
                    JOIN collector_group collector_role
                      ON collector_role.group_id = group_user.gid
                ),
                line_amounts AS (
                    SELECT
                        line.order_id,
                        SUM(CASE WHEN line.meter_line_type = 'consumption'
                            THEN line.product_uom_qty ELSE 0 END
                        ) AS consumption_kwh
                    FROM sale_order_line line
                    GROUP BY line.order_id
                ),
                payment_dates AS (
                    SELECT
                        allocation.sale_order_id,
                        SUM(CASE WHEN payment_move.date = CURRENT_DATE
                            THEN allocation.allocated_amount ELSE 0 END
                        ) AS today_collection,
                        MAX(payment_move.date) AS latest_payment_date
                    FROM utility_payment_allocation allocation
                    JOIN account_payment payment
                      ON payment.id = allocation.payment_id
                    JOIN account_move payment_move
                      ON payment_move.id = payment.move_id
                     AND payment_move.state = 'posted'
                    WHERE allocation.state = 'reconciled'
                      AND allocation.sale_order_id IS NOT NULL
                    GROUP BY allocation.sale_order_id
                ),
                sales AS (
                    SELECT
                        sale.date_range_id AS period_id,
                        collector.collector_id,
                        collector.company_id,
                        customer.region_id,
                        customer.area_id,
                        COUNT(sale.id)::integer AS invoice_count,
                        SUM(COALESCE(lines.consumption_kwh, 0)) AS consumption_kwh,
                        SUM(COALESCE(sale.amount_energy, 0)) AS sale_amount,
                        SUM(COALESCE(sale.amount_total, 0)) AS gross_sales,
                        SUM(
                            COALESCE(sale.amount_paid, 0)
                            - LEAST(
                                COALESCE(payments.today_collection, 0),
                                COALESCE(sale.amount_paid, 0)
                            )
                        ) AS cumulative_collection,
                        SUM(LEAST(
                            COALESCE(payments.today_collection, 0),
                            COALESCE(sale.amount_paid, 0)
                        )) AS today_collection,
                        SUM(COALESCE(sale.amount_paid, 0)) AS total_collection,
                        COUNT(sale.id) FILTER (
                            WHERE COALESCE(sale.balance_due, 0) <= 0
                              AND payments.latest_payment_date <> CURRENT_DATE
                        )::integer AS cumulative_paid_invoices,
                        COUNT(sale.id) FILTER (
                            WHERE COALESCE(sale.balance_due, 0) <= 0
                              AND payments.latest_payment_date = CURRENT_DATE
                        )::integer AS today_paid_invoices,
                        COUNT(sale.id) FILTER (
                            WHERE COALESCE(sale.balance_due, 0) <= 0
                        )::integer AS total_paid_invoices,
                        SUM(COALESCE(sale.balance_due, 0)) AS remaining_sales,
                        COUNT(sale.id) FILTER (
                            WHERE COALESCE(sale.balance_due, 0) > 0
                        )::integer AS remaining_invoices
                    FROM sale_order sale
                    JOIN utility_customer customer
                      ON customer.id = sale.customer_id
                    JOIN collector_assignments collector
                      ON collector.route_id = customer.route_id
                     AND collector.company_id = sale.company_id
                    LEFT JOIN line_amounts lines ON lines.order_id = sale.id
                    LEFT JOIN payment_dates payments
                      ON payments.sale_order_id = sale.id
                    WHERE sale.state IN ('sale', 'done')
                      AND sale.date_range_id IS NOT NULL
                    GROUP BY sale.date_range_id, collector.collector_id,
                        collector.company_id, customer.region_id,
                        customer.area_id
                ),
                billing_adjustments AS (
                    SELECT
                        adjustment.billing_period_id AS period_id,
                        collector.collector_id,
                        collector.company_id,
                        customer.region_id,
                        customer.area_id,
                        0::integer AS invoice_count,
                        0::numeric AS consumption_kwh,
                        0::numeric AS sale_amount,
                        0::numeric AS gross_sales,
                        0::numeric AS cumulative_collection,
                        0::numeric AS today_collection,
                        0::numeric AS total_collection,
                        0::integer AS cumulative_paid_invoices,
                        0::integer AS today_paid_invoices,
                        0::integer AS total_paid_invoices,
                        0::numeric AS remaining_sales,
                        0::integer AS remaining_invoices
                    FROM utility_billing_adjustment adjustment
                    JOIN utility_customer customer
                      ON customer.id = adjustment.customer_id
                    JOIN collector_assignments collector
                      ON collector.route_id = customer.route_id
                     AND collector.company_id = adjustment.company_id
                    WHERE adjustment.state IN ('approved', 'applied')
                      AND adjustment.billing_period_id IS NOT NULL
                    GROUP BY adjustment.billing_period_id,
                        collector.collector_id, collector.company_id,
                        customer.region_id, customer.area_id
                ),
                report_rows AS (
                    SELECT * FROM sales
                    UNION ALL
                    SELECT * FROM billing_adjustments
                ),
                aggregated AS (
                    SELECT
                        period_id,
                        collector_id,
                        company_id,
                        region_id,
                        area_id,
                        SUM(invoice_count)::integer AS invoice_count,
                        SUM(consumption_kwh) AS consumption_kwh,
                        SUM(sale_amount) AS sale_amount,
                        SUM(gross_sales) AS gross_sales,
                        SUM(cumulative_collection) AS cumulative_collection,
                        SUM(today_collection) AS today_collection,
                        SUM(total_collection) AS total_collection,
                        SUM(cumulative_paid_invoices)::integer
                            AS cumulative_paid_invoices,
                        SUM(today_paid_invoices)::integer
                            AS today_paid_invoices,
                        SUM(total_paid_invoices)::integer
                            AS total_paid_invoices,
                        SUM(remaining_sales) AS remaining_sales,
                        SUM(remaining_invoices)::integer
                            AS remaining_invoices
                    FROM report_rows
                    GROUP BY period_id, collector_id, company_id,
                        region_id, area_id
                )
                SELECT
                    row_number() OVER (
                        ORDER BY period_id DESC, collector_id
                    )::integer AS id,
                    period_id,
                    collector_id,
                    company_id,
                    region_id,
                    area_id,
                    invoice_count,
                    consumption_kwh,
                    sale_amount,
                    gross_sales,
                    cumulative_collection,
                    today_collection,
                    total_collection,
                    CASE WHEN gross_sales <> 0
                        THEN total_collection * 100.0 / gross_sales
                        ELSE 0 END AS collection_rate,
                    cumulative_paid_invoices,
                    today_paid_invoices,
                    total_paid_invoices,
                    CASE WHEN invoice_count <> 0
                        THEN total_paid_invoices * 100.0 / invoice_count
                        ELSE 0 END AS paid_invoice_rate,
                    remaining_sales,
                    remaining_invoices
                FROM aggregated
            )
        """)
