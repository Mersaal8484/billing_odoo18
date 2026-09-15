"""pre-migrate: تهيئة حالة الفترات المخططة وحل تكرار الفترات المفتوحة.

- يغير القيمة الافتراضية لأعمدة reading_state و collection_state إلى 'planned'.
- يحدّث جميع السجلات التي حالتها state = 'planned' لتصبح reading_state = 'planned' و collection_state = 'planned'.
- يضمن عدم وجود أكثر من فترة قراءة مفتوحة أو فترة تحصيل مفتوحة لنفس الدورية والشركة
  قبل تفعيل القيد البرمجي الصارم.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    _logger.info('utility_core 16.0.1.8.0 pre-migrate: starting period state cleanup')

    # 1. تحديث القيمة الافتراضية في قاعدة البيانات
    cr.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'date_range' AND column_name = 'reading_state'
            ) THEN
                ALTER TABLE date_range ALTER COLUMN reading_state SET DEFAULT 'planned';
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'date_range' AND column_name = 'collection_state'
            ) THEN
                ALTER TABLE date_range ALTER COLUMN collection_state SET DEFAULT 'planned';
            END IF;
        END $$;
    """)

    # 2. تحديث السجلات المخططة (state = 'planned') لتكون بحالة planned أيضاً
    cr.execute("""
        UPDATE date_range
        SET reading_state = 'planned'
        WHERE state = 'planned' OR reading_state IS NULL OR reading_state = '';
    """)
    _logger.info('utility_core 16.0.1.8.0 pre-migrate: updated planned reading states (%d rows)', cr.rowcount)

    cr.execute("""
        UPDATE date_range
        SET collection_state = 'planned'
        WHERE state = 'planned' OR collection_state IS NULL OR collection_state = '';
    """)
    _logger.info('utility_core 16.0.1.8.0 pre-migrate: updated planned collection states (%d rows)', cr.rowcount)

    # 3. معالجة أي تكرار تاريخي لفترات مفتوحة لنفس الدورية والشركة:
    # إبقاء أحدث فترة مفتوحة فقط، وإغلاق الفترات الأقدم لتفادي تعارض القيد
    cr.execute("""
        WITH ranked_open_reading AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY company_id, billing_cadence
                       ORDER BY date_start DESC, id DESC
                   ) as rn
            FROM date_range
            WHERE active = TRUE
              AND period_role = 'reading'
              AND reading_state = 'open'
        )
        UPDATE date_range
        SET reading_state = 'closed'
        WHERE id IN (
            SELECT id FROM ranked_open_reading WHERE rn > 1
        );
    """)
    if cr.rowcount > 0:
        _logger.warning(
            'utility_core 16.0.1.8.0 pre-migrate: closed %d duplicate open reading periods',
            cr.rowcount
        )

    cr.execute("""
        WITH ranked_open_collection AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY company_id, billing_cadence
                       ORDER BY date_start DESC, id DESC
                   ) as rn
            FROM date_range
            WHERE active = TRUE
              AND period_role = 'reading'
              AND collection_state = 'open'
        )
        UPDATE date_range
        SET collection_state = 'reconciled'
        WHERE id IN (
            SELECT id FROM ranked_open_collection WHERE rn > 1
        );
    """)
    if cr.rowcount > 0:
        _logger.warning(
            'utility_core 16.0.1.8.0 pre-migrate: reconciled %d duplicate open collection periods',
            cr.rowcount
        )

    _logger.info('utility_core 16.0.1.8.0 pre-migrate: period state cleanup finished successfully')
