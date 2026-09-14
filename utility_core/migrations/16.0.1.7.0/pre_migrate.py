"""pre-migrate: إضافة أعمدة الدورة الموحدة إلى جدول date_range.

يُنفَّذ قبل تحديث ORM حتى لا تفشل إعادة الكتابة على قاعدة البيانات.
الأعمدة مضافة بـ IF NOT EXISTS لضمان الـ idempotency.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Add unified-cycle columns to date_range if they do not already exist."""
    _logger.info(
        'utility_core pre-migrate: adding unified-cycle columns to date_range'
    )

    statements = [
        # نطاق الدفع الصريح داخل سجل الدورة الموحد
        "ALTER TABLE date_range ADD COLUMN IF NOT EXISTS payment_start date",
        "ALTER TABLE date_range ADD COLUMN IF NOT EXISTS payment_end date",
        # حالة القراءة المستقلة
        "ALTER TABLE date_range ADD COLUMN IF NOT EXISTS reading_state varchar(32) DEFAULT 'open'",
        # حالة التحصيل المستقلة
        "ALTER TABLE date_range ADD COLUMN IF NOT EXISTS collection_state varchar(32) DEFAULT 'open'",
        # تواريخ الإغلاق/المطابقة
        "ALTER TABLE date_range ADD COLUMN IF NOT EXISTS reading_closed_at timestamp without time zone",
        "ALTER TABLE date_range ADD COLUMN IF NOT EXISTS collection_reconciled_at timestamp without time zone",
    ]

    for sql in statements:
        _logger.debug('utility_core pre-migrate: %s', sql)
        cr.execute(sql)

    # إضافة فهارس لتحسين الأداء
    index_statements = [
        """CREATE INDEX IF NOT EXISTS date_range_reading_state_idx
           ON date_range (reading_state) WHERE active = TRUE""",
        """CREATE INDEX IF NOT EXISTS date_range_collection_state_idx
           ON date_range (collection_state) WHERE active = TRUE""",
        """CREATE INDEX IF NOT EXISTS date_range_payment_dates_idx
           ON date_range (payment_start, payment_end) WHERE payment_start IS NOT NULL""",
    ]
    for sql in index_statements:
        try:
            cr.execute(sql)
        except Exception as e:
            _logger.warning('utility_core pre-migrate: index creation skipped: %s', e)

    _logger.info(
        'utility_core pre-migrate: unified-cycle columns added successfully'
    )
