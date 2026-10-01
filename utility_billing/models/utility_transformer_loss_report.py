from odoo import fields, models, tools


class UtilityTransformerLossReport(models.Model):
    _name = 'utility.transformer.loss.report'
    _description = 'تقرير الفاقد للمحولات جميع الفترات'
    _auto = False
    _rec_name = 'transformer_id'
    _order = 'period_start desc, transformer_id'

    company_id = fields.Many2one('res.company', string='الشركة', readonly=True)
    date_range_id = fields.Many2one('date.range', string='الفترة', readonly=True)
    period_start = fields.Date(string='تاريخ بداية الفترة', readonly=True)
    period_end = fields.Date(string='تاريخ نهاية الفترة', readonly=True)

    region_id = fields.Many2one('utility.region', string='المنطقة', readonly=True)
    area_id = fields.Many2one('utility.region', string='المنطقة الفرعية', readonly=True)
    substation_id = fields.Many2one('utility.substation', string='المحطة', readonly=True)
    feeder_id = fields.Many2one('utility.feeder', string='الفيدر / الخلية', readonly=True)
    transformer_id = fields.Many2one('utility.transformer', string='المحول', readonly=True)
    transformer_reading_id = fields.Many2one('utility.reading', string='قراءة المحول', readonly=True)

    transformer_code = fields.Char(string='رمز المحول', readonly=True)
    transformer_name = fields.Char(string='اسم المحول', readonly=True)

    previous_reading = fields.Float(string='القراءة السابقة', readonly=True)
    current_reading = fields.Float(string='القراءة الحالية', readonly=True)
    energy_sent = fields.Float(string='الطاقة المرسلة', readonly=True)
    energy_sold = fields.Float(string='الطاقة المباعة', readonly=True)
    loss_kwh = fields.Float(string='الفاقد', readonly=True)
    loss_percent = fields.Float(string='نسبة الفاقد %', readonly=True, aggregator='avg')
    customer_count = fields.Integer(string='عدد المشتركين', readonly=True)
    invoice_count = fields.Integer(string='عدد الفواتير', readonly=True)
    amount_total = fields.Monetary(string='إجمالي الفواتير', readonly=True, currency_field='currency_id')
    balance_due = fields.Monetary(string='إجمالي المتبقي', readonly=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='العملة', readonly=True)

    def init(self):
        """Create an aggregated SQL view for transformer loss across all periods.

        The view aggregates bills and transformer readings once per
        (company, period, transformer). This avoids slow per-row Python loops
        and prevents duplicates caused by repeated joins in pivot reports.
        """
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS utility_reading_transformer_period_report_idx
                ON utility_reading (company_id, date_range_id, transformer_id, reading_date DESC, id DESC)
                WHERE reading_category = 'transformer'
                  AND reading_purpose = 'periodic'
                  AND transformer_id IS NOT NULL
                  AND date_range_id IS NOT NULL;
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS sale_order_utility_customer_period_report_idx
                ON sale_order (company_id, date_range_id, customer_id)
                WHERE customer_id IS NOT NULL
                  AND date_range_id IS NOT NULL
                  AND state <> 'cancel';
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS utility_customer_transformer_report_idx
                ON utility_customer (transformer_id)
                WHERE transformer_id IS NOT NULL;
        """)

        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW utility_transformer_loss_report AS (
                WITH billed AS (
                    SELECT
                        so.company_id,
                        so.date_range_id,
                        reading.transformer_snapshot_id AS transformer_id,
                        COUNT(so.id)::integer AS invoice_count,
                        COUNT(DISTINCT so.customer_id)::integer AS customer_count,
                        SUM(COALESCE(so.consumption, 0.0))::double precision AS energy_sold,
                        SUM(COALESCE(so.amount_total, 0.0))::double precision AS amount_total,
                        SUM(COALESCE(so.balance_due, 0.0))::double precision AS balance_due
                    FROM sale_order so
                    JOIN utility_reading reading ON reading.id = so.reading_id
                    WHERE so.reading_id IS NOT NULL
                      AND so.date_range_id IS NOT NULL
                      AND reading.transformer_snapshot_id IS NOT NULL
                      AND so.state <> 'cancel'
                    GROUP BY so.company_id, so.date_range_id, reading.transformer_snapshot_id
                ),
                ranked_transformer_readings AS (
                    SELECT
                        reading.id,
                        reading.company_id,
                        reading.date_range_id,
                        reading.transformer_snapshot_id AS transformer_id,
                        reading.previous_reading,
                        reading.reading_value,
                        reading.consumption,
                        ROW_NUMBER() OVER (
                            PARTITION BY reading.company_id, reading.date_range_id, reading.transformer_snapshot_id
                            ORDER BY
                                CASE
                                    WHEN reading.state IN ('approved', 'billed') THEN 0
                                    WHEN reading.state = 'queued' THEN 1
                                    ELSE 2
                                END,
                                reading.reading_date DESC,
                                reading.id DESC
                        ) AS row_number
                    FROM utility_reading reading
                    WHERE reading.reading_category = 'transformer'
                      AND reading.reading_purpose = 'periodic'
                      AND reading.transformer_snapshot_id IS NOT NULL
                      AND reading.date_range_id IS NOT NULL
                      AND COALESCE(reading.is_private_transformer, FALSE) = FALSE
                      AND reading.state IN ('approved', 'billed', 'queued')
                ),
                transformer_readings AS (
                    SELECT
                        id AS transformer_reading_id,
                        company_id,
                        date_range_id,
                        transformer_id,
                        previous_reading,
                        reading_value AS current_reading,
                        consumption AS energy_sent
                    FROM ranked_transformer_readings
                    WHERE row_number = 1
                ),
                report_keys AS (
                    SELECT company_id, date_range_id, transformer_id FROM billed
                    UNION
                    SELECT company_id, date_range_id, transformer_id FROM transformer_readings
                )
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY date_period.date_start DESC NULLS LAST, keyset.transformer_id, keyset.company_id
                    )::integer AS id,
                    keyset.company_id,
                    keyset.date_range_id,
                    date_period.date_start AS period_start,
                    date_period.date_end AS period_end,
                    transformer.region_id,
                    transformer.area_id,
                    transformer.substation_id,
                    transformer.feeder_id,
                    keyset.transformer_id,
                    reading.transformer_reading_id,
                    transformer.code AS transformer_code,
                    transformer.name AS transformer_name,
                    COALESCE(reading.previous_reading, 0.0)::double precision AS previous_reading,
                    COALESCE(reading.current_reading, 0.0)::double precision AS current_reading,
                    COALESCE(reading.energy_sent, 0.0)::double precision AS energy_sent,
                    COALESCE(billed.energy_sold, 0.0)::double precision AS energy_sold,
                    (
                        COALESCE(reading.energy_sent, 0.0) - COALESCE(billed.energy_sold, 0.0)
                    )::double precision AS loss_kwh,
                    CASE
                        WHEN COALESCE(reading.energy_sent, 0.0) <> 0.0 THEN
                            ROUND((
                                (
                                    COALESCE(reading.energy_sent, 0.0)
                                    - COALESCE(billed.energy_sold, 0.0)
                                ) * 100.0 / NULLIF(reading.energy_sent, 0.0)
                            )::numeric, 2)::double precision
                        ELSE 0.0
                    END AS loss_percent,
                    COALESCE(billed.customer_count, 0)::integer AS customer_count,
                    COALESCE(billed.invoice_count, 0)::integer AS invoice_count,
                    COALESCE(billed.amount_total, 0.0)::double precision AS amount_total,
                    COALESCE(billed.balance_due, 0.0)::double precision AS balance_due,
                    company.currency_id
                FROM report_keys keyset
                JOIN utility_transformer transformer ON transformer.id = keyset.transformer_id
                LEFT JOIN res_company company ON company.id = keyset.company_id
                LEFT JOIN date_range date_period ON date_period.id = keyset.date_range_id
                LEFT JOIN billed
                    ON billed.company_id = keyset.company_id
                   AND billed.date_range_id = keyset.date_range_id
                   AND billed.transformer_id = keyset.transformer_id
                LEFT JOIN transformer_readings reading
                    ON reading.company_id = keyset.company_id
                   AND reading.date_range_id = keyset.date_range_id
                   AND reading.transformer_id = keyset.transformer_id
                WHERE transformer.active IS TRUE
            )
        """)
