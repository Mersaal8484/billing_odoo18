from odoo import fields, models, tools


class UtilityEnergySentReport(models.Model):
    """Period balance between a feeder coupling meter and its customers."""

    _name = 'utility.energy.sent.report'
    _description = 'Energy Sent and Loss Report'
    _auto = False
    _rec_name = 'feeder_id'
    _order = 'period_start desc, region_id, feeder_id'

    company_id = fields.Many2one('res.company', readonly=True)
    date_range_id = fields.Many2one('date.range', string='الفترة', readonly=True)
    period_start = fields.Date(string='بداية الفترة', readonly=True)
    period_end = fields.Date(string='نهاية الفترة', readonly=True)
    region_id = fields.Many2one('utility.region', string='المنطقة', readonly=True)
    area_id = fields.Many2one('utility.region', string='المنطقة الفرعية', readonly=True)
    substation_id = fields.Many2one('utility.substation', string='المحطة الفرعية', readonly=True)
    feeder_id = fields.Many2one('utility.feeder', string='الخلية / الفيدر', readonly=True)
    feeder_code = fields.Char(string='رمز الخلية', readonly=True)
    feeder_name = fields.Char(string='اسم الخلية', readonly=True)
    feeder_reading_id = fields.Many2one('utility.reading', string='قراءة عداد الخلية', readonly=True)
    energy_sent = fields.Float(string='الطاقة المرسلة', readonly=True)
    energy_sold = fields.Float(string='الطاقة المباعة', readonly=True)
    total_loss = fields.Float(string='الفاقد', readonly=True)
    total_loss_percent = fields.Float(string='نسبة الفاقد %', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS utility_reading_feeder_period_report_idx
                ON utility_reading (company_id, date_range_id, feeder_id, reading_date DESC, id DESC)
                WHERE reading_category = 'feeder'
                  AND reading_purpose = 'periodic'
                  AND feeder_id IS NOT NULL
                  AND date_range_id IS NOT NULL
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS utility_reading_customer_transformer_period_report_idx
                ON utility_reading (company_id, date_range_id, transformer_snapshot_id, meter_id,
                                    reading_date DESC, id DESC)
                WHERE reading_category = 'customer'
                  AND reading_purpose = 'periodic'
                  AND transformer_snapshot_id IS NOT NULL
                  AND date_range_id IS NOT NULL
        """)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW utility_energy_sent_report AS (
                WITH ranked_feeder_readings AS (
                    SELECT reading.id, reading.company_id, reading.date_range_id, reading.feeder_id,
                           reading.previous_reading, reading.reading_value, reading.consumption,
                           ROW_NUMBER() OVER (
                               PARTITION BY reading.company_id, reading.date_range_id, reading.feeder_id
                               ORDER BY CASE WHEN reading.state IN ('approved', 'billed') THEN 0
                                             WHEN reading.state = 'queued' THEN 1 ELSE 2 END,
                                        reading.reading_date DESC, reading.id DESC
                           ) AS row_number
                    FROM utility_reading reading
                    JOIN utility_feeder feeder ON feeder.id = reading.feeder_id
                    WHERE reading.reading_category = 'feeder'
                      AND reading.reading_purpose = 'periodic'
                      AND reading.date_range_id IS NOT NULL
                      AND feeder.coupling_meter_id IS NOT NULL
                      AND reading.meter_id = feeder.coupling_meter_id
                      AND reading.state IN ('approved', 'billed', 'queued')
                ),
                feeder_readings AS (
                    SELECT id, company_id, date_range_id, feeder_id,
                           COALESCE(consumption, 0.0) AS energy_sent
                    FROM ranked_feeder_readings
                    WHERE row_number = 1
                ),
                ranked_customer_readings AS (
                    SELECT reading.company_id, reading.date_range_id,
                           reading.transformer_snapshot_id, reading.meter_id,
                           COALESCE(reading.consumption, 0.0) AS energy_sold,
                           ROW_NUMBER() OVER (
                               PARTITION BY reading.company_id, reading.date_range_id, reading.meter_id
                               ORDER BY CASE WHEN reading.state IN ('approved', 'billed') THEN 0
                                             WHEN reading.state = 'queued' THEN 1 ELSE 2 END,
                                        reading.reading_date DESC, reading.id DESC
                           ) AS row_number
                    FROM utility_reading reading
                    WHERE reading.reading_category = 'customer'
                      AND reading.reading_purpose = 'periodic'
                      AND reading.date_range_id IS NOT NULL
                      AND reading.transformer_snapshot_id IS NOT NULL
                      AND reading.state IN ('approved', 'billed', 'queued')
                ),
                sold_energy_by_feeder AS (
                    SELECT reading.company_id, reading.date_range_id, transformer.feeder_id,
                           SUM(reading.energy_sold) AS energy_sold
                    FROM ranked_customer_readings reading
                    JOIN utility_transformer transformer
                        ON transformer.id = reading.transformer_snapshot_id
                    WHERE reading.row_number = 1
                      AND transformer.feeder_id IS NOT NULL
                    GROUP BY reading.company_id, reading.date_range_id, transformer.feeder_id
                ),
                report_keys AS (
                    SELECT company_id, date_range_id, feeder_id FROM feeder_readings
                    UNION
                    SELECT company_id, date_range_id, feeder_id FROM sold_energy_by_feeder
                )
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY period.date_start DESC, report_keys.company_id, report_keys.feeder_id
                    ) AS id,
                    report_keys.company_id, report_keys.date_range_id,
                    period.date_start AS period_start, period.date_end AS period_end,
                    feeder.region_id, feeder.area_id, feeder.substation_id,
                    feeder.id AS feeder_id, feeder.code AS feeder_code, feeder.name AS feeder_name,
                    feeder_readings.id AS feeder_reading_id,
                    COALESCE(feeder_readings.energy_sent, 0.0) AS energy_sent,
                    COALESCE(sold_energy_by_feeder.energy_sold, 0.0) AS energy_sold,
                    COALESCE(feeder_readings.energy_sent, 0.0)
                        - COALESCE(sold_energy_by_feeder.energy_sold, 0.0) AS total_loss,
                    CASE WHEN COALESCE(feeder_readings.energy_sent, 0.0) = 0.0 THEN 0.0
                   ELSE ROUND((
                         (
                                 COALESCE(feeder_readings.energy_sent, 0.0)
                                 - COALESCE(sold_energy_by_feeder.energy_sold, 0.0)
                             ) * 100.0 / feeder_readings.energy_sent
                         )::numeric, 2)::double precision
                    END AS total_loss_percent
                FROM report_keys
                JOIN utility_feeder feeder ON feeder.id = report_keys.feeder_id
                JOIN date_range period ON period.id = report_keys.date_range_id
                LEFT JOIN feeder_readings
                    ON feeder_readings.company_id = report_keys.company_id
                   AND feeder_readings.date_range_id = report_keys.date_range_id
                   AND feeder_readings.feeder_id = report_keys.feeder_id
                LEFT JOIN sold_energy_by_feeder
                    ON sold_energy_by_feeder.company_id = report_keys.company_id
                   AND sold_energy_by_feeder.date_range_id = report_keys.date_range_id
                   AND sold_energy_by_feeder.feeder_id = report_keys.feeder_id
            )
        """)
